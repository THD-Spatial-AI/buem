import time
import logging
from buem.thermal.model_buem import ModelBUEM
from buem.results.standard_plots import PlotVariables as pvar
from buem.config.cfg_attribute import cfg
from buem.config.validator import validate_cfg
import numpy as np
import sys

logger = logging.getLogger(__name__)


def run_model(cfg_dict, plot: bool = False, use_milp: bool = False, return_models: bool = False):
    """
    Run the ISO 52016 single-pass dead-band thermal model and return results.

    One ModelBUEM instance is created and sim_model() is called once.  The
    single-pass QP simultaneously determines heating AND cooling demand:
    - heating_load[i] > 0  when T_air would fall below comfortT_lb without HVAC
    - cooling_load[i] < 0  when T_air would rise above comfortT_ub without HVAC
    - both zero            in passive comfort (dead-band) hours

    Parameters
    ----------
    cfg_dict : dict
        Normalised configuration accepted by ModelBUEM.
    plot : bool, optional
        If True, attempt to plot results after the run (best-effort).
    use_milp : bool, optional
        If True use the experimental MILP solver path.
    return_models : bool, optional
        If True include the ModelBUEM instance in the returned dict under key 'model'.
    """
    start_time = time.time()

    if cfg_dict is None:
        raise ValueError("cfg_dict must be provided to run_model")

    issues = validate_cfg(cfg_dict)
    if issues:
        raise ValueError("Configuration validation failed: " + "; ".join(issues))

    try:
        model = ModelBUEM(cfg_dict)
        model.sim_model(use_milp=use_milp)
        elapsed = time.time() - start_time

        if plot:
            try:
                plotter = pvar()
                plotter.plot_variables(model, model, period='year')
            except Exception:
                import traceback
                traceback.print_exc()

        out = {
            "times": model.times,
            "heating": model.heating_load.copy(),
            "cooling": model.cooling_load.copy(),
            "elapsed_s": elapsed,
        }
        if return_models:
            out["model"] = model
        return out

    except Exception as exc:
        raise RuntimeError(f"Model run failed: {exc}") from exc

def main():
    try:
        res = run_model(cfg, plot=True, use_milp=False, return_models=True)
    except ValueError as ve:
        print("Configuration validation error:", ve)
        sys.exit(2)
    except RuntimeError as re:
        print("Model execution error:", re)
        sys.exit(3)

    heating = res["heating"]
    cooling = res["cooling"]

    print(f"Heating load total: {heating.sum():.1f} kWh/yr")
    print(f"Cooling load total: {cooling.sum():.1f} kWh/yr")
    print(f"Execution time:     {res['elapsed_s']:.2f} s")

    total_abs = float(np.sum(heating) + np.sum(np.abs(cooling)))
    print(f"Total HVAC (heating + |cooling|): {total_abs:.1f} kWh/yr")

    model = res.get("model")
    if model is not None:
        print("\n=== Diagnostics ===\n")
        model.diagnostics_solar_components()
        try:
            floor_area = getattr(model, 'bA_f', None) or float(model.cfg.get('A_ref', 1.0))
            print(f" Heating per A_ref ({floor_area:.0f} m²): {heating.sum()/floor_area:.1f} kWh/m²/yr")
            print(f" Cooling per A_ref ({floor_area:.0f} m²): {abs(cooling.sum())/floor_area:.1f} kWh/m²/yr")
            print(f" bU (U-values W/m2K): {model.bU}")
            print(f" bH (kW/K): {model.bH}")
        except Exception as _e:
            print("Could not print low-level params:", _e)

    n_total = len(res["times"])
    heat_active   = np.asarray(heating) > 0.0
    cool_active   = np.asarray(cooling) < 0.0
    both_active   = heat_active & cool_active
    print(f"\nOperation (year, {n_total} h): heating_hours={int(heat_active.sum())}, "
          f"cooling_hours={int(cool_active.sum())}, simultaneous={int(both_active.sum())}")


if __name__=="__main__":
    main()