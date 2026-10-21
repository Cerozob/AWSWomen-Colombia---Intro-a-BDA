#!/usr/bin/env python3
"""Entrada del CDK: lee config.json, aplica tags y conecta los paquetes de cdk-nag."""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aws_cdk as cdk  # noqa: E402
import cdk_nag  # noqa: E402
from bda_ats.config import RAIZ, cargar  # noqa: E402
from bda_ats.stack import BdaAtsStack  # noqa: E402

PAQUETES_NAG = {
    "aws_solutions": cdk_nag.AwsSolutionsChecks,
    "hipaa_security": cdk_nag.HIPAASecurityChecks,
    "nist_800_53_r4": cdk_nag.NIST80053R4Checks,
    "nist_800_53_r5": cdk_nag.NIST80053R5Checks,
    "pci_dss_321": cdk_nag.PCIDSS321Checks,
    "serverless": cdk_nag.ServerlessChecks,
}


def construir_frontend() -> Path:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("No encontré pnpm en el PATH; se necesita para compilar el frontend.")
    frontend = RAIZ / "frontend"
    # La salida va a stderr: stdout del app de CDK no debe llevar texto extra.
    subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=frontend, check=True, stdout=sys.stderr)
    subprocess.run([pnpm, "build"], cwd=frontend, check=True, stdout=sys.stderr)
    dist = frontend / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("El build de Vite terminó sin frontend/dist/index.html.")
    return dist


def construir_app(app: cdk.App) -> cdk.App:
    config = cargar()

    # Cada synth/deploy compila el frontend, así nunca se despliega un build viejo.
    # Las pruebas lo omiten con -c omitirFrontend=true.
    if app.node.try_get_context("omitirFrontend") in (True, "true"):
        dist_frontend = None
    else:
        dist_frontend = construir_frontend()

    BdaAtsStack(
        app,
        "BdaAtsStack",
        config=config,
        dist_frontend=dist_frontend,
        env=cdk.Environment(account=config.cuenta, region=config.region),
        description="Demo ATS de hojas de vida con Amazon Bedrock Data Automation",
    )

    for llave, valor in config.tags.items():
        cdk.Tags.of(app).add(llave, valor)

    for flag, paquete in PAQUETES_NAG.items():
        if config.nag[flag]:
            cdk.Validations.of(app).add_plugins(paquete(app))

    return app


if __name__ == "__main__":
    construir_app(cdk.App()).synth()
