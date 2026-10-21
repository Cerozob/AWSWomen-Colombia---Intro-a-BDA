"""Lambda Python 3.13 ARM64 con el código de backend/ empaquetado (función + comun/ + dependencias).

El empaquetado intenta primero localmente con `uv` (sin Docker) instalando ruedas para
manylinux ARM64; si `uv` no está, cae a Docker con la imagen de build de Lambda.
"""

import shutil
import subprocess
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, Duration, ILocalBundling, RemovalPolicy
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from bda_ats.config import RAIZ

BACKEND = RAIZ / "backend"
EXCLUIR = ["tests", "**/__pycache__", "**/*.pyc", ".pytest_cache"]


@jsii.implements(ILocalBundling)
class _EmpaquetadoLocalUv:
    def __init__(self, nombre: str) -> None:
        self._nombre = nombre

    def try_bundle(self, output_dir: str, *args, **kwargs) -> bool:
        uv = shutil.which("uv")
        if not uv:
            return False
        salida = Path(output_dir)
        origen = BACKEND / "funciones" / self._nombre
        requisitos = origen / "requirements.txt"
        if requisitos.exists():
            subprocess.run(
                [
                    uv, "pip", "install", "--quiet",
                    "-r", str(requisitos),
                    "--target", str(salida),
                    "--python-platform", "aarch64-manylinux2014",
                    "--python-version", "3.13",
                    "--only-binary", ":all:",
                ],
                check=True,
            )
        for archivo in origen.glob("*.py"):
            shutil.copy2(archivo, salida / archivo.name)
        shutil.copytree(
            BACKEND / "comun",
            salida / "comun",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        return True


class FuncionPython(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        nombre: str,
        descripcion: str,
        entorno: dict[str, str] | None = None,
        timeout_s: int = 30,
    ) -> None:
        super().__init__(scope, id)

        self.log_group = logs.LogGroup(
            self,
            "Logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        comando_docker = (
            f"pip install -q -r funciones/{nombre}/requirements.txt -t /asset-output"
            f" && cp funciones/{nombre}/*.py /asset-output/"
            " && cp -r comun /asset-output/"
        )
        codigo = lambda_.Code.from_asset(
            str(BACKEND),
            exclude=EXCLUIR,
            bundling=BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                platform="linux/arm64",
                command=["bash", "-c", comando_docker],
                local=_EmpaquetadoLocalUv(nombre),
            ),
        )

        self.funcion = lambda_.Function(
            self,
            "Funcion",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="app.handler",
            code=codigo,
            memory_size=512,
            timeout=Duration.seconds(timeout_s),
            description=descripcion,
            tracing=lambda_.Tracing.ACTIVE,
            log_group=self.log_group,
            environment={
                "POWERTOOLS_SERVICE_NAME": nombre,
                "POWERTOOLS_LOG_LEVEL": "INFO",
                **(entorno or {}),
            },
        )
