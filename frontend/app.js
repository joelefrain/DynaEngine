'use strict';

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview && window.pywebview.api;

const ui = {
  state: null,
  selectedSection: '',
  selectedFailure: '',
  activeMaterialIndex: null,
};

function escapeHtml(value){
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function cssEscape(value){
  if(window.CSS && CSS.escape) return CSS.escape(String(value));
  return String(value).replace(/["\\]/g, '\\$&');
}
function num(value, fallback=0){ const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function fmt(value, digits=2){ const n = Number(value); return Number.isFinite(n) ? n.toFixed(digits).replace(/\.0+$/,'').replace(/(\.\d*?)0+$/,'$1') : '—'; }
function backendAvailable(){ return !!api(); }

function normalizeState(next){
  ui.state = next || ui.state || {};
  const s = ui.state;
  s.section_names ||= [];
  s.section_previews ||= {};
  s.x_position_map ||= {};
  s.number_of_columns ||= {total:0};
  s.materials ||= [];
  s.material_names ||= [];
  s.dynamic_curve_config ||= {};
  s.warnings ||= [];
  s.warning_area_ids ||= [];
  s.warning_area_map ||= {};
  s.warning_section_messages ||= {};
  s.error_section_messages ||= {};
  s.logs ||= [];
  s.results ||= {};
  if(!ui.selectedSection || !s.section_names.includes(ui.selectedSection)) ui.selectedSection = s.section_names[0] || '';
  const failures = failureSurfaces(ui.selectedSection);
  if(!ui.selectedFailure || !failures.some(f => f.id === ui.selectedFailure)) ui.selectedFailure = failures[0]?.id || 'failure_1';
}

async function call(name, ...args){
  try{
    if(!backendAvailable()) throw new Error('pywebview no está disponible. Ejecuta app.py o el ejecutable portable.');
    const next = await api()[name](...args);
    normalizeState(next);
    render();
    return ui.state;
  }catch(err){
    console.error(err);
    showNotice('Error llamando backend local: ' + (err?.message || err));
    return ui.state;
  }
}

function preview(section){ return ui.state?.section_previews?.[section] || null; }
function failureSurfaces(section){
  const p = preview(section);
  return (p?.failure_surfaces?.length ? p.failure_surfaces : [{id:'failure_1', label:'Superficie 1', color:'#d3342f'}]);
}
function sectionXMap(section){ return ui.state?.x_position_map?.[section] || {}; }
function valuesFor(section, failure){ return sectionXMap(section)[failure] || []; }
function totalForSection(section){ return Object.values(sectionXMap(section)).reduce((a,v)=>a+(Array.isArray(v)?v.length:0),0); }
function canEditColumns(){ return !!(ui.state?.metadata_ready && !ui.state?.metadata_error); }
function canGoMaterials(){ return !!(ui.state?.metadata_ready && (ui.state?.number_of_columns?.total || 0) > 0 && ui.state.materials.length); }
function materialComplete(m){
  const vs = m?.shear_velocity || {};
  return !!(m?.characterization_status === 'Completo' && m?.dynamic_model?.model_type && Array.isArray(vs.depth) && Array.isArray(vs.vs) && vs.depth.length && vs.depth.length === vs.vs.length);
}
function canGoAnalysis(){ return canGoMaterials() && ui.state.materials.every(materialComplete); }

function switchView(view){
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav,.side').forEach(el => el.classList.remove('active'));
  $(`view-${view}`)?.classList.add('active');
  document.querySelectorAll(`[data-view="${view}"]`).forEach(el => el.classList.add('active'));
  call('set_current_view', view);
}

function render(){
  if(!ui.state) return;
  $('statusText').textContent = ui.state.processing ? `Procesando ${ui.state.progress_pct || 0}%` : `Sesión ${ui.state.session_id || 'local'}`;
  renderMetadataStatus();
  renderSections();
  renderPreview();
  renderFailures();
  renderColumns();
  renderMaterials();
  renderAnalysis();
  updateGates();
}

function renderMetadataStatus(){
  const s = ui.state;
  const box = $('metadataStatusBox');
  let cls = 'metadata-pending';
  let title = 'Lectura DXF pendiente';
  let detail = s.metadata_status || 'Selecciona una carpeta DXF para ejecutar send_metadata_from_sections.';
  if(s.metadata_error){ cls = 'metadata-error'; title = 'Error en send_metadata_from_sections'; detail = s.metadata_error; }
  else if(s.metadata_needs_confirmation){ cls = 'metadata-warning'; title = 'Warnings detectados por send_metadata_from_sections'; }
  else if(s.metadata_ready){ cls = 'metadata-ok'; title = 'Metadata DXF validada'; }
  const action = s.metadata_needs_confirmation ? '<button id="btnReviewWarningsInline" class="btn-small">Revisar warnings</button>' : '';
  box.className = `metadata-status ${cls}`;
  box.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span>${action}`;
  $('btnReviewWarningsInline')?.addEventListener('click', showWarningDecisionModal);
}

function renderSections(){
  const s = ui.state;
  const list = $('sectionsList');
  const select = $('sectionSelect');
  const thumbs = $('thumbnails');
  select.innerHTML = '';
  thumbs.innerHTML = '';
  if(!s.section_names.length){
    list.innerHTML = '<div class="muted">Sin secciones DXF cargadas.</div>';
    $('galleryCount').textContent = '0 secciones';
    $('warningsBox').textContent = 'Sin lectura ejecutada.';
    return;
  }
  list.innerHTML = s.section_names.map(name => `<div class="item ${name===ui.selectedSection?'active':''}" data-section="${escapeHtml(name)}"><b>${escapeHtml(name)}</b><small>${totalForSection(name)} coordenada(s) X · ${failureSurfaces(name).length} superficie(s)</small></div>`).join('');
  list.querySelectorAll('[data-section]').forEach(el => el.addEventListener('click', () => selectSection(el.dataset.section)));
  select.innerHTML = s.section_names.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
  select.value = ui.selectedSection;
  $('galleryCount').textContent = `${s.section_names.length} sección(es)`;
  s.section_names.forEach(name => {
    const p = preview(name);
    const el = document.createElement('div');
    el.className = 'thumbnail' + (name === ui.selectedSection ? ' active' : '');
    el.innerHTML = `<div class="thumb-svg">${p?.svg || '<div class="empty-preview">DXF</div>'}</div><div class="thumbnail-label">${escapeHtml(name)}</div>${totalForSection(name)?`<div class="thumbnail-badge">${totalForSection(name)}</div>`:''}`;
    el.addEventListener('click', () => selectSection(name));
    thumbs.appendChild(el);
  });
  $('warningsBox').innerHTML = s.warnings.length ? s.warnings.map(w => `<div>• ${escapeHtml(w)}</div>`).join('') : '<span class="muted">Sin warnings registrados.</span>';
}

function selectSection(name){
  ui.selectedSection = name;
  ui.selectedFailure = failureSurfaces(name)[0]?.id || 'failure_1';
  render();
}

function renderPreview(){
  const host = $('previewHost');
  const p = preview(ui.selectedSection);
  host.innerHTML = p?.svg || '<div class="empty-preview large">Selecciona una carpeta DXF.</div>';
  highlightWarningAreas(host, ui.selectedSection);
  bindFailureSelection(host);
}

function renderFailures(){
  const select = $('failureSelect');
  const failures = failureSurfaces(ui.selectedSection);
  select.innerHTML = failures.map(f => `<option value="${escapeHtml(f.id)}">${escapeHtml(f.label || f.id)}</option>`).join('');
  select.value = ui.selectedFailure;
  const active = failures.find(f => f.id === ui.selectedFailure);
  $('failureInfo').innerHTML = active ? `<span class="swatch" style="background:${active.color || '#d3342f'}"></span>${escapeHtml(active.layer || active.label || active.id)}` : '';
  applyFailureFocus($('previewHost'));
}

function bindFailureSelection(host){
  host.querySelectorAll('[data-failure]').forEach(el => {
    el.addEventListener('click', ev => {
      ev.stopPropagation();
      ui.selectedFailure = el.getAttribute('data-failure');
      render();
    });
  });
  applyFailureFocus(host);
}
function applyFailureFocus(host){
  if(!host) return;
  host.querySelectorAll('[data-failure]').forEach(el => {
    const active = el.getAttribute('data-failure') === ui.selectedFailure;
    el.classList.toggle('failure-active', active);
    el.classList.toggle('failure-dimmed', !active);
  });
}
function highlightWarningAreas(host, section){
  const ids = ui.state.warning_area_map?.[section] || [];
  ids.forEach(id => host.querySelectorAll(`[data-area-id="${cssEscape(id)}"]`).forEach(el => el.classList.add('warning-area-highlight')));
}

function bounds(){
  const b = preview(ui.selectedSection)?.bounds;
  return b || {min_x:0,max_x:100,min_y:0,max_y:100};
}
function renderColumns(){
  const b = bounds();
  const width = Math.max(b.max_x - b.min_x, 1);
  const height = Math.max(b.max_y - b.min_y, 1);
  $('columnOverlay').setAttribute('viewBox', `${b.min_x} ${b.min_y} ${width} ${height}`);
  const g = $('columnLines');
  g.innerHTML = '';
  failureSurfaces(ui.selectedSection).forEach(f => {
    const color = f.id === ui.selectedFailure ? '#d3342f' : '#64748b';
    valuesFor(ui.selectedSection, f.id).forEach((x, i) => {
      const xx = num(x);
      g.insertAdjacentHTML('beforeend', `<g class="column-mark ${f.id===ui.selectedFailure?'':'muted-mark'}"><line x1="${xx}" x2="${xx}" y1="${b.min_y}" y2="${b.max_y}" stroke="${color}"/><text x="${xx}" y="${b.min_y + height * 0.08}" dx="5">${escapeHtml(f.id)} · ${fmt(xx,2)}</text></g>`);
    });
  });
  const activeValues = valuesFor(ui.selectedSection, ui.selectedFailure);
  $('columnSummary').textContent = canEditColumns() ? `X en superficie activa: ${activeValues.length} | Sección: ${totalForSection(ui.selectedSection)} | Total: ${ui.state.number_of_columns.total || 0}` : 'La edición se habilita cuando metadata_ready sea true. Acepta warnings si corresponde.';
  renderColumnTable(activeValues);
}
function renderColumnTable(values){
  const body = $('columnTableBody');
  if(!canEditColumns()){
    body.innerHTML = '<tr><td colspan="4" class="muted empty-row">Primero ejecuta send_metadata_from_sections y acepta/corrige warnings.</td></tr>';
    return;
  }
  body.innerHTML = values.length ? values.map((x,i) => `<tr><td>${i+1}</td><td>${escapeHtml(ui.selectedFailure)}</td><td><input class="column-x-input" data-i="${i}" type="number" step="0.01" value="${fmt(x,2)}"></td><td><button class="btn-icon" data-remove="${i}">Eliminar</button></td></tr>`).join('') : '<tr><td colspan="4" class="muted empty-row">Haz clic en el DXF para agregar X.</td></tr>';
  body.querySelectorAll('[data-remove]').forEach(btn => btn.addEventListener('click', () => call('remove_column', ui.selectedSection, ui.selectedFailure, Number(btn.dataset.remove))));
  body.querySelectorAll('.column-x-input').forEach(inp => inp.addEventListener('change', () => {
    const next = [...values]; next[Number(inp.dataset.i)] = Number(inp.value);
    call('set_columns', ui.selectedSection, ui.selectedFailure, next);
  }));
}

function svgPointFromEvent(svg, event){
  const pt = svg.createSVGPoint();
  pt.x = event.clientX; pt.y = event.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}
function addColumnFromClick(event){
  if(!canEditColumns()) return showNotice(ui.state.metadata_error || 'Acepta/corrige warnings antes de editar columnas.');
  const pt = svgPointFromEvent($('columnOverlay'), event);
  call('add_column', ui.selectedSection, ui.selectedFailure, Number(pt.x.toFixed(4)));
}
function addColumnFromInput(){
  const x = Number($('manualX').value);
  if(!Number.isFinite(x)) return showNotice('Ingresa una coordenada X válida.');
  call('add_column', ui.selectedSection, ui.selectedFailure, Number(x.toFixed(4)));
  $('manualX').value = '';
}

function modelLabel(type){ return ui.state.dynamic_curve_config?.[type]?.model_name || type || 'No seleccionado'; }
function materialRows(){ return ui.state.materials || []; }
function renderMaterials(){
  const tbody = document.querySelector('#materialsTable tbody');
  if(!tbody) return;
  const materials = materialRows();
  if(!materials.length){ tbody.innerHTML = '<tr><td colspan="7" class="muted empty-row">Sin materiales leídos desde metadata.</td></tr>'; return; }
  tbody.innerHTML = materials.map((m,i) => `<tr><td><b>${escapeHtml(m.material_name)}</b></td><td>${fmt(m.unit_weight_kn_m3,2)}</td><td>${fmt(m.shear_properties?.c,2)}</td><td>${fmt(m.shear_properties?.phi,2)}</td><td>${escapeHtml(modelLabel(m.dynamic_model?.model_type))}</td><td><span class="material-status ${materialComplete(m)?'ok':'pending'}">${materialComplete(m)?'Completo':'Pendiente'}</span></td><td><button class="btn-small" data-material-index="${i}">Caracterizar</button></td></tr>`).join('');
  tbody.querySelectorAll('[data-material-index]').forEach(btn => btn.addEventListener('click', () => openMaterialModal(Number(btn.dataset.materialIndex))));
}
function normalizeMaterial(m){
  m ||= {};
  return {material_name:m.material_name || 'Material', unit_weight_kn_m3:num(m.unit_weight_kn_m3,19), shear_properties:{c:num(m.shear_properties?.c,0), phi:num(m.shear_properties?.phi,34)}, shear_velocity:{depth:m.shear_velocity?.depth || [0], vs:m.shear_velocity?.vs || [300]}, dynamic_model:{model_type:m.dynamic_model?.model_type || '', sigma_vertical:num(m.dynamic_model?.sigma_vertical,100), soil_group:m.dynamic_model?.soil_group || '', soil_parameters:m.dynamic_model?.soil_parameters || {}, data:m.dynamic_model?.data || null}, characterization_status:m.characterization_status || 'Pendiente'};
}
function openMaterialModal(index){
  ui.activeMaterialIndex = index;
  ui.state.materials[index] = normalizeMaterial(ui.state.materials[index]);
  const m = ui.state.materials[index];
  $('materialModalTitle').textContent = `Caracterizar material: ${m.material_name}`;
  $('matName').value = m.material_name; $('matGamma').value = m.unit_weight_kn_m3; $('matC').value = m.shear_properties.c; $('matPhi').value = m.shear_properties.phi; $('matSigma').value = m.dynamic_model.sigma_vertical;
  renderDynamicModelSelect(m); renderVsTable(m); renderCurveTable(m); updatePlots(); showModal('materialModal');
}
function closeMaterialModal(){ hideModal('materialModal'); ui.activeMaterialIndex = null; }
function currentMaterial(){ return ui.activeMaterialIndex === null ? null : ui.state.materials[ui.activeMaterialIndex]; }
function renderDynamicModelSelect(m){
  const select = $('dynamicModelSelect');
  const cfg = ui.state.dynamic_curve_config || {};
  select.innerHTML = '<option value="">No seleccionado</option>' + Object.entries(cfg).map(([k,v]) => `<option value="${escapeHtml(k)}">${escapeHtml(v.model_name || k)}</option>`).join('');
  select.value = m.dynamic_model.model_type || '';
  renderDynamicParams(m);
}
function defaultsFor(type, group){
  const cfg = ui.state.dynamic_curve_config?.[type] || {};
  let defs = cfg.model_parameters || {};
  if(cfg.model_type === 'by_group') defs = defs[group || cfg.allowable_groups?.[0]] || {};
  const out = {};
  Object.entries(defs).forEach(([k,d]) => out[k] = d.type === 'enum' ? (d.options?.[0] || '') : (d.min_value ?? 0));
  return out;
}
function paramDefs(type, group){
  const cfg = ui.state.dynamic_curve_config?.[type] || {};
  return cfg.model_type === 'by_group' ? (cfg.model_parameters?.[group] || {}) : (cfg.model_parameters || {});
}
function renderDynamicParams(m){
  const type = $('dynamicModelSelect').value;
  const cfg = ui.state.dynamic_curve_config?.[type] || {};
  m.dynamic_model.model_type = type;
  if(cfg.model_type === 'by_group'){
    const groups = cfg.allowable_groups || Object.keys(cfg.model_parameters || {});
    $('dynamicGroupLabel').classList.remove('hidden');
    $('dynamicGroupSelect').innerHTML = groups.map(g => `<option value="${escapeHtml(g)}">${escapeHtml(g.replaceAll('_',' '))}</option>`).join('');
    if(!groups.includes(m.dynamic_model.soil_group)) m.dynamic_model.soil_group = groups[0] || '';
    $('dynamicGroupSelect').value = m.dynamic_model.soil_group;
  }else{
    $('dynamicGroupLabel').classList.add('hidden');
    m.dynamic_model.soil_group = '';
  }
  if(type && Object.keys(m.dynamic_model.soil_parameters || {}).length === 0) m.dynamic_model.soil_parameters = defaultsFor(type, m.dynamic_model.soil_group);
  const defs = paramDefs(type, m.dynamic_model.soil_group);
  $('dynamicParamsHost').innerHTML = Object.entries(defs).map(([k,d]) => `<label>${escapeHtml(d.screen_name || k)}${d.unit?' ('+escapeHtml(d.unit)+')':''}<input data-dyn-param="${escapeHtml(k)}" type="number" step="any" value="${escapeHtml(m.dynamic_model.soil_parameters?.[k] ?? d.min_value ?? 0)}"></label>`).join('') || '<div class="muted">Sin parámetros editables.</div>';
  $('dynamicParamsHost').querySelectorAll('[data-dyn-param]').forEach(inp => inp.addEventListener('input', () => m.dynamic_model.soil_parameters[inp.dataset.dynParam] = Number(inp.value)));
  $('userCurvesPanel').classList.toggle('hidden', type !== 'user_defined');
}
function renderVsTable(m){
  const depth = m.shear_velocity.depth || [];
  const vs = m.shear_velocity.vs || [];
  const n = Math.max(depth.length, vs.length, 1);
  $('vsTableBody').innerHTML = Array.from({length:n}).map((_,i) => `<tr><td><input data-vs-depth="${i}" type="number" step="0.01" value="${depth[i] ?? ''}"></td><td><input data-vs-value="${i}" type="number" step="0.01" value="${vs[i] ?? ''}"></td><td><button class="btn-icon" data-remove-vs="${i}">×</button></td></tr>`).join('') + '<tr><td colspan="3"><button id="btnAddVsRow" class="btn-add-row">Agregar fila</button></td></tr>';
  $('vsTableBody').querySelectorAll('input').forEach(inp => inp.addEventListener('input', updatePlots));
  $('vsTableBody').querySelectorAll('[data-remove-vs]').forEach(btn => btn.addEventListener('click', () => { const rows=readVsRows(); rows.splice(Number(btn.dataset.removeVs),1); m.shear_velocity={depth:rows.map(r=>r.depth),vs:rows.map(r=>r.vs)}; renderVsTable(m); updatePlots(); }));
  $('btnAddVsRow')?.addEventListener('click', () => { const rows=readVsRows(); rows.push({depth:rows.length?rows.at(-1).depth+1:0, vs:rows.length?rows.at(-1).vs:300}); m.shear_velocity={depth:rows.map(r=>r.depth),vs:rows.map(r=>r.vs)}; renderVsTable(m); updatePlots(); });
}
function readVsRows(){
  const rows=[]; $('vsTableBody').querySelectorAll('tr').forEach(tr => { const d=Number(tr.querySelector('[data-vs-depth]')?.value); const v=Number(tr.querySelector('[data-vs-value]')?.value); if(Number.isFinite(d)&&Number.isFinite(v)) rows.push({depth:d,vs:v}); });
  return rows.sort((a,b)=>a.depth-b.depth);
}
function defaultCurveRows(){ return [{strain:0.0001,ggmax:0.98,damping:1.5},{strain:0.001,ggmax:0.88,damping:3},{strain:0.01,ggmax:0.55,damping:8},{strain:0.1,ggmax:0.22,damping:18}]; }
function renderCurveTable(m){
  const rows = m.dynamic_model.data?.rows || defaultCurveRows();
  m.dynamic_model.data = {rows};
  $('curveTableBody').innerHTML = rows.map((r,i)=>`<tr><td><input data-curve-strain="${i}" type="number" step="any" value="${r.strain}"></td><td><input data-curve-ggmax="${i}" type="number" step="any" value="${r.ggmax}"></td><td><input data-curve-damping="${i}" type="number" step="any" value="${r.damping}"></td><td><button class="btn-icon" data-remove-curve="${i}">×</button></td></tr>`).join('');
  $('curveTableBody').querySelectorAll('input').forEach(inp => inp.addEventListener('input', updatePlots));
  $('curveTableBody').querySelectorAll('[data-remove-curve]').forEach(btn => btn.addEventListener('click', () => { const rows=readCurveRows(); rows.splice(Number(btn.dataset.removeCurve),1); m.dynamic_model.data={rows}; renderCurveTable(m); updatePlots(); }));
}
function readCurveRows(){
  const rows=[]; $('curveTableBody').querySelectorAll('tr').forEach(tr => { const strain=Number(tr.querySelector('[data-curve-strain]')?.value); const ggmax=Number(tr.querySelector('[data-curve-ggmax]')?.value); const damping=Number(tr.querySelector('[data-curve-damping]')?.value); if(strain>0 && Number.isFinite(ggmax) && Number.isFinite(damping)) rows.push({strain,ggmax,damping}); });
  return rows.sort((a,b)=>a.strain-b.strain);
}
function saveMaterial(){
  const m = currentMaterial(); if(!m) return;
  m.material_name = $('matName').value.trim() || m.material_name;
  m.unit_weight_kn_m3 = Number($('matGamma').value);
  m.shear_properties = {c:Number($('matC').value), phi:Number($('matPhi').value)};
  m.dynamic_model.model_type = $('dynamicModelSelect').value;
  m.dynamic_model.sigma_vertical = Number($('matSigma').value);
  if(!$('dynamicGroupLabel').classList.contains('hidden')) m.dynamic_model.soil_group = $('dynamicGroupSelect').value;
  document.querySelectorAll('[data-dyn-param]').forEach(inp => m.dynamic_model.soil_parameters[inp.dataset.dynParam] = Number(inp.value));
  const rows = readVsRows(); m.shear_velocity = {depth:rows.map(r=>r.depth), vs:rows.map(r=>r.vs)};
  if(m.dynamic_model.model_type === 'user_defined') m.dynamic_model.data = {rows:readCurveRows()};
  m.characterization_status = materialComplete({...m, characterization_status:'Completo'}) ? 'Completo' : 'Pendiente';
  if(m.dynamic_model.model_type && rows.length) m.characterization_status = 'Completo';
  call('set_materials', ui.state.materials);
  closeMaterialModal();
}

function plotSimple(hostId, rows, xKey, yKey, title){
  const host = $(hostId); if(!host) return;
  if(!rows.length){ host.innerHTML = '<div class="empty-preview">Sin datos</div>'; return; }
  const w=420,h=260,l=54,r=20,t=30,b=40;
  const xs=rows.map(r=>Number(r[xKey])), ys=rows.map(r=>Number(r[yKey]));
  const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
  const X=x=>l+(x-minX)/(maxX-minX||1)*(w-l-r), Y=y=>t+(maxY-y)/(maxY-minY||1)*(h-t-b);
  const path=rows.map((r,i)=>`${i?'L':'M'} ${X(r[xKey])} ${Y(r[yKey])}`).join(' ');
  host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" class="vector-plot"><rect width="${w}" height="${h}" fill="#fff"/><line x1="${l}" y1="${t}" x2="${l}" y2="${h-b}" class="plot-axis"/><line x1="${l}" y1="${h-b}" x2="${w-r}" y2="${h-b}" class="plot-axis"/><text x="${w/2}" y="18" text-anchor="middle" class="plot-title">${escapeHtml(title)}</text><path d="${path}" class="plot-line"/>${rows.map(r=>`<circle cx="${X(r[xKey])}" cy="${Y(r[yKey])}" r="3" class="plot-point"/>`).join('')}</svg>`;
}
function updatePlots(){ plotSimple('vsPlot', readVsRows(), 'vs', 'depth', 'Perfil Vs'); if(!$('userCurvesPanel').classList.contains('hidden')){ const rows=readCurveRows(); plotSimple('ggmaxPlot', rows, 'strain', 'ggmax', 'G/Gmax'); plotSimple('dampingPlot', rows, 'strain', 'damping', 'Amortiguamiento'); } }

function analysisSpecs(){ return ui.state.results?.column_input_specs || buildFallbackSpecs(); }
function buildFallbackSpecs(){
  const specs=[];
  (ui.state.section_names || []).forEach(section => Object.entries(sectionXMap(section)).forEach(([failure,xs]) => (xs || []).forEach((x,i) => specs.push({id:`${section}-column_${i+1}-${failure}`, section, failure, column:`column_${i+1}`, x, layers:[]}))));
  return specs;
}
function renderAnalysis(){
  if($('progressBar')) $('progressBar').style.width = `${ui.state.progress_pct || 0}%`;
  if($('processStatusText')) $('processStatusText').textContent = ui.state.processing ? 'Procesamiento en ejecución.' : (Object.keys(ui.state.results||{}).length ? 'Procesamiento finalizado.' : 'Aún no iniciado.');
  if($('fTarget')) $('fTarget').value = ui.state.f_target || 25;
  const specs = analysisSpecs();
  $('analysisInputTables').innerHTML = specs.length ? specs.map(s => `<article class="column-input-card"><b>${escapeHtml(s.id)}</b><small>${escapeHtml(s.section)} · ${escapeHtml(s.failure)} · X=${fmt(s.x,2)}</small><table class="table compact"><thead><tr><th>#</th><th>Material</th><th>Espesor</th></tr></thead><tbody>${(s.layers||[]).map((r,i)=>`<tr><td>${i+1}</td><td>${escapeHtml(r.material || r.material_name || '')}</td><td>${fmt(r.thickness,3)}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">Se completará al ejecutar.</td></tr>'}</tbody></table></article>`).join('') : '<p class="muted">Define coordenadas X para generar input.</p>';
  const rows = [];
  if(ui.state.results?.session_dir) rows.push(['Carpeta de sesión', ui.state.results.session_dir]);
  rows.push(['Columnas definidas', String(specs.length)]);
  $('resultsTableHost').innerHTML = `<table class="table compact"><tbody>${rows.map(r=>`<tr><td>${escapeHtml(r[0])}</td><td>${escapeHtml(r[1])}</td></tr>`).join('')}</tbody></table>`;
  $('resultBox').textContent = JSON.stringify(ui.state.results || {}, null, 2);
}

function updateGates(){
  $('btnGoMaterials').disabled = !canGoMaterials();
  $('btnGoAnalysis').disabled = !canGoAnalysis();
  $('btnStartProcess').disabled = !canGoAnalysis() || ui.state.processing;
}

function showModal(id){ const m=$(id); m?.classList.add('active'); m?.setAttribute('aria-hidden','false'); }
function hideModal(id){ const m=$(id); m?.classList.remove('active'); m?.setAttribute('aria-hidden','true'); }
function showNotice(message){ alert(message); }
function showWarningDecisionModal(){
  $('warningDecisionText').textContent = 'El backend reportó warnings durante send_metadata_from_sections. Revisa las secciones y acepta solo si corresponde continuar.';
  $('warningReviewList').innerHTML = (ui.state.section_names || []).map(name => {
    const warnings = ui.state.warning_section_messages?.[name] || [];
    const errors = ui.state.error_section_messages?.[name] || [];
    const ids = ui.state.warning_area_map?.[name] || [];
    if(!warnings.length && !errors.length && !ids.length) return '';
    return `<div class="warning-review-item"><div><b>${escapeHtml(name)}</b><p>${escapeHtml(errors[0] || warnings[0] || 'Revisar sección.')}</p><small>Áreas: ${ids.map(id=>'#'+id).join(', ') || 'sin ID'}</small></div><button class="btn-small" data-preview-section="${escapeHtml(name)}">Ver</button></div>`;
  }).join('') || '<div class="muted">Warnings globales sin sección específica.</div>';
  $('warningMessageList').innerHTML = (ui.state.warnings || []).map(w=>`<div>• ${escapeHtml(w)}</div>`).join('');
  $('warningReviewList').querySelectorAll('[data-preview-section]').forEach(btn => btn.addEventListener('click', () => openSectionPreview(btn.dataset.previewSection)));
  showModal('warningModal');
}
function openSectionPreview(section){
  $('sectionPreviewTitle').textContent = section;
  $('sectionPreviewWarningText').innerHTML = [...(ui.state.error_section_messages?.[section] || []), ...(ui.state.warning_section_messages?.[section] || [])].map(m=>`<div>• ${escapeHtml(m)}</div>`).join('') || '<span class="muted">Sin mensaje específico.</span>';
  $('sectionPreviewHost').innerHTML = preview(section)?.svg || '<div class="empty-preview">Sin preview</div>';
  highlightWarningAreas($('sectionPreviewHost'), section);
  const ids = ui.state.warning_area_map?.[section] || [];
  $('sectionPreviewAreas').innerHTML = ids.map(id=>`<span>Área ${escapeHtml(id)}</span>`).join('');
  showModal('sectionPreviewModal');
}
function renderLogBox(){ $('logBox').innerHTML = (ui.state.logs || []).map(l=>`<div class="log-${String(l.level).toLowerCase()}">[${escapeHtml(l.ts)}] ${escapeHtml(l.level)}: ${escapeHtml(l.message)}</div>`).join('') || '<div class="muted">Sin logs.</div>'; $('logBox').scrollTop = $('logBox').scrollHeight; }

async function selectAndLoadSections(){ $('loadingBar').classList.remove('hidden'); try{ await call('choose_sections_dir'); if(ui.state.metadata_needs_confirmation) showWarningDecisionModal(); } finally { $('loadingBar').classList.add('hidden'); } }

window.addEventListener('DOMContentLoaded', async () => {
  document.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));
  $('btnChooseSections').addEventListener('click', selectAndLoadSections);
  $('sectionSelect').addEventListener('change', () => selectSection($('sectionSelect').value));
  $('failureSelect').addEventListener('change', () => { ui.selectedFailure = $('failureSelect').value; render(); });
  $('geometryCanvas').addEventListener('click', addColumnFromClick);
  $('btnAddManualX').addEventListener('click', addColumnFromInput);
  $('manualX').addEventListener('keydown', e => { if(e.key === 'Enter') addColumnFromInput(); });
  $('btnClearColumns').addEventListener('click', () => call('clear_columns', ui.selectedSection, ui.selectedFailure));
  $('btnGoMaterials').addEventListener('click', () => canGoMaterials() ? switchView('materiales') : showNotice('Primero valida metadata, acepta warnings y define columnas.'));
  $('btnSaveMaterials').addEventListener('click', () => call('set_materials', ui.state.materials));
  $('btnGoAnalysis').addEventListener('click', async () => { await call('set_materials', ui.state.materials); if(canGoAnalysis()) switchView('analisis'); });
  $('btnCloseMaterialModal').addEventListener('click', closeMaterialModal);
  $('btnCancelMaterial').addEventListener('click', closeMaterialModal);
  $('btnSaveMaterialCharacterization').addEventListener('click', saveMaterial);
  $('dynamicModelSelect').addEventListener('change', () => { const m=currentMaterial(); if(m){ m.dynamic_model.soil_parameters={}; renderDynamicParams(m); renderCurveTable(m); updatePlots(); }});
  $('dynamicGroupSelect').addEventListener('change', () => { const m=currentMaterial(); if(m){ m.dynamic_model.soil_group=$('dynamicGroupSelect').value; m.dynamic_model.soil_parameters=defaultsFor(m.dynamic_model.model_type,m.dynamic_model.soil_group); renderDynamicParams(m); }});
  $('btnAddCurveRow').addEventListener('click', () => { const m=currentMaterial(); const rows=readCurveRows(); rows.push({strain:rows.length?rows.at(-1).strain*3:0.0001, ggmax:rows.length?rows.at(-1).ggmax:0.9, damping:rows.length?rows.at(-1).damping:2}); m.dynamic_model.data={rows}; renderCurveTable(m); updatePlots(); });
  $('warningCancel').addEventListener('click', () => hideModal('warningModal'));
  $('warningContinue').addEventListener('click', async () => { hideModal('warningModal'); await call('confirm_metadata_warnings'); });
  $('btnCloseSectionPreview').addEventListener('click', () => hideModal('sectionPreviewModal'));
  $('btnOpenLogs').addEventListener('click', () => { renderLogBox(); showModal('logsModal'); });
  $('btnCloseLogs').addEventListener('click', () => hideModal('logsModal'));
  $('btnStartProcess').addEventListener('click', async () => { await call('set_f_target', Number($('fTarget').value)); await call('start_column_process'); });
  $('btnSaveResults').addEventListener('click', () => call('save_results_as'));
  document.querySelectorAll('.modal').forEach(m => m.addEventListener('click', e => { if(e.target === m) hideModal(m.id); }));

  if(backendAvailable()) normalizeState(await api().get_state()); else normalizeState({metadata_status:'Ejecuta app.py para conectar con pywebview.', materials:[], section_names:[]});
  render();
  setInterval(async () => { if(backendAvailable()){ normalizeState(await api().get_state()); render(); } }, 1000);
});
