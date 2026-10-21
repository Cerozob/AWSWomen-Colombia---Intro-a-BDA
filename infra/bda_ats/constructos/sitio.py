"""Sitio web (React) en S3 privado detrás de CloudFront con OAC."""

from pathlib import Path
from typing import Any

from aws_cdk import RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct


class Sitio(Construct):
    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        self.bucket = s3.Bucket(
            self,
            "SitioBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # SPA: cualquier ruta desconocida devuelve index.html.
        spa = [
            cloudfront.ErrorResponse(http_status=codigo, response_http_status=200,
                                     response_page_path="/index.html")
            for codigo in (403, 404)
        ]
        self.distribucion = cloudfront.Distribution(
            self,
            "Distribucion",
            comment="ATS BDA demo",
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            error_responses=spa,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
            ),
        )
        self.url = f"https://{self.distribucion.distribution_domain_name}"

    def desplegar(self, dist: Path | None, config_web: dict[str, Any]) -> None:
        """Sube el build de Vite y el config.json que la app lee al arrancar."""
        fuentes = [s3deploy.Source.json_data("config.json", config_web)]
        if dist is not None:
            fuentes.insert(0, s3deploy.Source.asset(str(dist)))
        s3deploy.BucketDeployment(
            self,
            "Despliegue",
            sources=fuentes,
            destination_bucket=self.bucket,
            distribution=self.distribucion,
            distribution_paths=["/*"],
            memory_limit=512,
        )
