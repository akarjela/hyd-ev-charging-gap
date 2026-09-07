"""hydgap: fetch | build | optimize | serve"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from hydgap.config import DEFAULT_CONFIG, PROJECT_ROOT, load_config

app = typer.Typer(add_completion=False, help="Charging-infrastructure gap analysis for Hyderabad's electric two-wheelers.")

RAW = PROJECT_ROOT / "data" / "raw"
PROCESSED = PROJECT_ROOT / "data" / "processed"
ConfigOpt = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Model config YAML")


@app.command()
def fetch(config: Path = ConfigOpt, out: Path = RAW / "ocm_stations.json", max_results: int = 2000) -> None:
    """Pull chargers for the configured bounding box from OpenChargeMap (needs OCM_API_KEY)."""
    from hydgap.ingest.ocm import fetch_stations

    key = os.environ.get("OCM_API_KEY", "")
    if not key:
        typer.echo("OCM_API_KEY is not set. Free key: https://openchargemap.org/site/profile/applications", err=True)
        raise typer.Exit(2)
    cfg = load_config(config)
    n = fetch_stations(cfg.bbox, key, out, max_results=max_results)
    typer.echo(f"fetched {n} POIs into {out}")


@app.command()
def build(config: Path = ConfigOpt, raw: Path = RAW, out: Path = PROCESSED) -> None:
    """Grid, score and rank from the cached raw data; write data/processed."""
    from hydgap.pipeline import build_artifacts

    meta = build_artifacts(load_config(config), raw, out)
    w, s, c = meta["wards"], meta["stations"], meta["coverage"]
    typer.echo(f"wards: {w['found']}/{w['expected']} present; missing {w['missing']}; duplicates {w['duplicates']}")
    typer.echo(f"population: {meta['population']['matched']} wards matched, {len(meta['population']['unmatched'])} without a census row")
    typer.echo(f"stations: {s['kept']} kept of {s['total']} ({s['dropped_no_coords']} without coordinates, {s['unknown_status']} unknown status)")
    typer.echo(f"grid: {meta['grid']['n_cells']} H3 cells at res {meta['grid']['h3_resolution']}; demand mode {meta['demand']['mode']}")
    typer.echo(
        f"coverage: mean score {c['mean_score']:.3f}; {c['share_cells_covered']:.1%} of cells covered; "
        f"{c['share_cells_zero_chargers']:.1%} have no charger within radius; median nearest {c['median_nearest_m']:.0f} m"
    )


@app.command()
def optimize(
    budget: float = typer.Option(None, help="Total budget (defaults to optimizer.default_budget)"),
    site_cost: float = typer.Option(None, help="Cost per site (defaults to optimizer.site_cost)"),
    config: Path = ConfigOpt,
    processed: Path = PROCESSED,
    out: Path = typer.Option(None, help="Write proposed sites as GeoJSON here"),
) -> None:
    """Greedy siting on the built artifacts; prints the marginal-gain table."""
    from hydgap.optimize import SOLVERS, UniformCost, build_problem
    from hydgap.pipeline import load_artifacts
    from hydgap.spatial.crs import to_wgs84

    cfg = load_config(config)
    art = load_artifacts(processed)
    b = budget if budget is not None else cfg.optimizer.default_budget
    c = site_cost if site_cost is not None else cfg.optimizer.site_cost
    problem = build_problem(art.cells, cfg, b, UniformCost(c))
    result = SOLVERS[cfg.optimizer.method]().solve(problem)

    typer.echo(f"baseline covered demand {result.baseline_covered:.2f} of {result.total_demand:.2f}")
    typer.echo(f"{'#':>3} {'cell':<16} {'ward':>5} {'gain':>10} {'cumulative':>11} {'spent':>7}")
    ward_of = art.cells.set_index("h3")["ward_no"]
    for s in result.sites:
        typer.echo(f"{s.order:>3} {s.cell_id:<16} {int(ward_of[s.cell_id]):>5} {s.marginal_gain:>10.2f} {s.cumulative_gain:>11.2f} {s.spent:>7.1f}")
    typer.echo(f"after: {result.covered_after:.2f} covered ({result.covered_after / max(result.total_demand, 1e-9):.1%}), spent {result.spent:.1f}")

    if out:
        chosen = art.cells[art.cells["h3"].isin([s.cell_id for s in result.sites])].copy()
        chosen = chosen.set_geometry(chosen.geometry.centroid)
        order = {s.cell_id: s for s in result.sites}
        chosen["order"] = [order[h].order for h in chosen["h3"]]
        chosen["marginal_gain"] = [order[h].marginal_gain for h in chosen["h3"]]
        to_wgs84(chosen[["h3", "ward_no", "order", "marginal_gain", "geometry"]]).sort_values("order").to_file(out, driver="GeoJSON")
        typer.echo(f"wrote {out}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, processed: Path = PROCESSED, config: Path = ConfigOpt, reload: bool = False) -> None:
    """Serve the API and the map."""
    import uvicorn

    os.environ["HYDGAP_PROCESSED"] = str(processed)
    os.environ["HYDGAP_CONFIG"] = str(config)
    uvicorn.run("hydgap.api.app:app", host=host, port=port, reload=reload)


@app.command()
def meta(processed: Path = PROCESSED) -> None:
    """Print build_meta.json."""
    typer.echo(json.dumps(json.loads((processed / "build_meta.json").read_text()), indent=1))


if __name__ == "__main__":
    app()
