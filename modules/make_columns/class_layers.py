class Layers:
    def __init__(
        self,
        material_name: list,
        shear_velocity: list,
        unit_weight_kn_m3: list,
        dynamic_curve: list,
        shear_properties: list,
    ):

        self.name = material_name
        self.vs_models = shear_velocity
        self.unit_weight = unit_weight_kn_m3
        self.dynamic_curve = dynamic_curve

        self.map = {
            name: {
                "vs": vs_model,
                "gamma": unit_w,
                "model": model,
                "shear_properties": sp,
            }
            for name, vs_model, unit_w, model, sp in zip(
                material_name,
                shear_velocity,
                unit_weight_kn_m3,
                dynamic_curve,
                shear_properties,
            )
        }
