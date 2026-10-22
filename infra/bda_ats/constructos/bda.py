"""Blueprint `hoja-de-vida` y proyecto de Bedrock Data Automation."""

import json

from aws_cdk import Stack
from aws_cdk import aws_bedrock as bedrock
from constructs import Construct

from bda_ats.config import RAIZ

RUTA_BLUEPRINT = RAIZ / "blueprints" / "hoja-de-vida.json"
P = bedrock.CfnDataAutomationProject


class Bda(Construct):
    def __init__(self, scope: Construct, id: str, *, prefijo: str, perfil: str) -> None:
        super().__init__(scope, id)
        stack = Stack.of(self)

        esquema = json.loads(RUTA_BLUEPRINT.read_text(encoding="utf-8"))
        self.blueprint = bedrock.CfnBlueprint(
            self,
            "Blueprint",
            blueprint_name=f"{prefijo}-hoja-de-vida",
            type="DOCUMENT",
            schema=esquema,
        )

        self.proyecto = bedrock.CfnDataAutomationProject(
            self,
            "Proyecto",
            project_name=f"{prefijo}-hojas-de-vida",
            project_description="ATS de hojas de vida: salida estándar + blueprint hoja-de-vida",
            standard_output_configuration=P.StandardOutputConfigurationProperty(
                document=P.DocumentStandardOutputConfigurationProperty(
                    extraction=P.DocumentStandardExtractionProperty(
                        granularity=P.DocumentExtractionGranularityProperty(
                            types=["DOCUMENT", "PAGE", "ELEMENT"]
                        ),
                        # Con cajas habilitadas BDA ubica cada elemento y recorta las figuras (crop_images).
                        bounding_box=P.DocumentBoundingBoxProperty(state="ENABLED"),
                    ),
                    generative_field=P.DocumentStandardGenerativeFieldProperty(state="ENABLED"),
                    output_format=P.DocumentOutputFormatProperty(
                        text_format=P.DocumentOutputTextFormatProperty(types=["MARKDOWN"]),
                        additional_file_format=P.DocumentOutputAdditionalFileFormatProperty(
                            state="DISABLED"
                        ),
                    ),
                ),
            ),
            custom_output_configuration=P.CustomOutputConfigurationProperty(
                blueprints=[
                    P.BlueprintItemProperty(
                        blueprint_arn=self.blueprint.attr_blueprint_arn,
                        blueprint_stage="LIVE",
                    )
                ]
            ),
            # Una foto de una hoja de vida impresa se procesa como documento, para que aplique el blueprint.
            override_configuration=P.OverrideConfigurationProperty(
                modality_routing=P.ModalityRoutingConfigurationProperty(
                    jpeg="DOCUMENT", png="DOCUMENT"
                )
            ),
        )

        self.proyecto_arn = self.proyecto.attr_project_arn
        self.perfil_arn = stack.format_arn(
            service="bedrock",
            resource="data-automation-profile",
            resource_name=perfil,
        )
        # El perfil es cross-Region: BDA puede atender el job desde otra región de EE. UU.
        self.perfil_arn_iam = stack.format_arn(
            service="bedrock",
            region="*",
            resource="data-automation-profile",
            resource_name=perfil,
        )
