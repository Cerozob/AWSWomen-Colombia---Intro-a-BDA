"""Cognito: User Pool con login administrado, auto-registro restringido y grupo de reclutamiento."""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from constructs import Construct

from bda_ats.config import Config
from bda_ats.constructos.funcion_python import FuncionPython

GRUPO_RECLUTAMIENTO = "reclutamiento"


class Auth(Construct):
    def __init__(self, scope: Construct, id: str, *, config: Config, url_sitio: str) -> None:
        super().__init__(scope, id)

        pre_signup = FuncionPython(
            self,
            "PreSignUp",
            nombre="pre_signup",
            descripcion="Rechaza registros con correos fuera de la lista permitida",
            timeout_s=5,
            entorno={
                "CORREOS_PERMITIDOS": ",".join(config.correos_permitidos),
                "DOMINIOS_PERMITIDOS": ",".join(config.dominios_permitidos),
            },
        ).funcion
        post_confirmacion = FuncionPython(
            self,
            "PostConfirmacion",
            nombre="post_confirmacion",
            descripcion="Agrega al grupo de reclutamiento los correos configurados",
            timeout_s=10,
            entorno={
                "CORREOS_RECLUTAMIENTO": ",".join(config.correos_reclutamiento),
                "GRUPO": GRUPO_RECLUTAMIENTO,
            },
        ).funcion

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{config.prefijo}-usuarios",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            lambda_triggers=cognito.UserPoolTriggers(
                pre_sign_up=pre_signup, post_confirmation=post_confirmacion
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        cognito.CfnUserPoolGroup(
            self,
            "GrupoReclutamiento",
            user_pool_id=self.user_pool.user_pool_id,
            group_name=GRUPO_RECLUTAMIENTO,
            description="Equipo de reclutamiento: ve todas las candidaturas",
        )
        # Política aparte (no la del rol por defecto) para no crear un ciclo:
        # el pool depende de la Lambda y este permiso depende del pool.
        iam.Policy(
            self,
            "PermisoAgregarAGrupo",
            roles=[post_confirmacion.role],
            statements=[
                iam.PolicyStatement(
                    actions=["cognito-idp:AdminAddUserToGroup"],
                    resources=[self.user_pool.user_pool_arn],
                )
            ],
        )

        # Login administrado de Cognito (managed login v2): las pantallas de inicio de
        # sesión, registro y recuperación las sirve Cognito, no la app.
        self.dominio = self.user_pool.add_domain(
            "Dominio",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{config.prefijo}-{config.cuenta}"
            ),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
        )

        url_retorno = f"{url_sitio}/"
        self.cliente = self.user_pool.add_client(
            "ClienteWeb",
            generate_secret=False,
            prevent_user_existence_errors=True,
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=[url_retorno],
                logout_urls=[url_retorno],
            ),
        )

        # Estilo por defecto de Cognito para las pantallas del login administrado.
        cognito.CfnManagedLoginBranding(
            self,
            "EstiloLogin",
            user_pool_id=self.user_pool.user_pool_id,
            client_id=self.cliente.user_pool_client_id,
            use_cognito_provided_values=True,
        )

        region = Stack.of(self).region
        self.dominio_login = f"{self.dominio.domain_name}.auth.{region}.amazoncognito.com"
