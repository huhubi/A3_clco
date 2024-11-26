import pulumi
import pulumi_azure_native.insights as insights
import pulumi_azure_native.resources as resource
import pulumi_azure_native.sql as sql
import pulumi_azure_native.storage as storage
import pulumi_azure_native.web as web
from pulumi import Config, Output, asset
from pulumi_azure_native.storage import BlobContainer, PublicAccess

# Set username and configuration
username = "pulumi"
config = Config()
pwd = config.require("sqlPassword")

# Create a resource group
resource_group = resource.ResourceGroup("appservicerg")

# Create a storage account
storage_account = storage.StorageAccount(
    "appservicesa",
    resource_group_name=resource_group.name,
    kind=storage.Kind.STORAGE_V2,
    sku=storage.SkuArgs(name=storage.SkuName.STANDARD_LRS))

# Create a Blob container
storage_container = BlobContainer(
    "appservice-container",
    account_name=storage_account.name,
    resource_group_name=resource_group.name,
    public_access=PublicAccess.NONE
)

# Upload the Flask application code to the storage account
blob = storage.Blob(
    "appservice-app",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
    container_name=storage_container.name,
    type=storage.BlobType.BLOCK,
    source=asset.FileAsset("app.py")
)

# Generate a SAS token for the blob
blob_sas = storage.list_storage_account_service_sas_output(
    account_name=storage_account.name,
    protocols=storage.HttpProtocol.HTTPS,
    shared_access_start_time="2021-01-01",
    shared_access_expiry_time="2030-01-01",
    resource=storage.SignedResource.C,
    resource_group_name=resource_group.name,
    permissions=storage.Permissions.R,
    canonicalized_resource=Output.concat("/blob/", storage_account.name, "/", storage_container.name),
    content_type="application/json",
    cache_control="max-age=5",
    content_disposition="inline",
    content_encoding="deflate"
)

# Construct the signed blob URL
signed_blob_url = Output.concat(
    "https://", storage_account.name, ".blob.core.windows.net/",
    storage_container.name, "/",
    blob.name, "?",
    blob_sas.service_sas_token
)

# Use WEBSITE_RUN_FROM_PACKAGE app setting to deploy from the signed URL
# Create Application Insights
app_insights = insights.Component(
    "appservice-ai",
    application_type=insights.ApplicationType.WEB,
    kind="web",
    ingestion_mode="applicationInsights",
    resource_group_name=resource_group.name)


# Create an App Service plan
app_service_plan = web.AppServicePlan(
    "appservice-asp",
    resource_group_name=resource_group.name,
    kind="Linux",
    reserved=True,
    sku=web.SkuDescriptionArgs(
        tier="Free",
        name="B1",
    ))

# Deploy the Flask application as a web app
app = web.WebApp(
    "appservice-flask",
    resource_group_name=resource_group.name,
    server_farm_id=app_service_plan.id,
    site_config=web.SiteConfigArgs(
        linux_fx_version="PYTHON|3.09",
        app_settings=[
            web.NameValuePairArgs(name="WEBSITE_RUN_FROM_PACKAGE", value=signed_blob_url),
            web.NameValuePairArgs(name="APPINSIGHTS_INSTRUMENTATIONKEY", value=app_insights.instrumentation_key),
            web.NameValuePairArgs(name="SCM_DO_BUILD_DURING_DEPLOYMENT", value="true"),
        ]
    )
)


# Export outputs
pulumi.export("web_app_url", pulumi.Output.concat("http://", app.default_host_name))
pulumi.export("scm_web_app_url", pulumi.Output.concat("http://", app.default_host_name.apply(lambda name: name.replace(".azurewebsites.net", ".scm.azurewebsites.net"))))
pulumi.export("log_tail_command", pulumi.Output.all(app.name, resource_group.name).apply(lambda args: f"az webapp log tail --name {args[0]} --resource-group {args[1]}"))
pulumi.export("web_ssh_url", pulumi.Output.concat("https://", app.default_host_name.apply(lambda name: name.replace(".azurewebsites.net", ".scm.azurewebsites.net")), "/webssh/host"))
pulumi.export("deploy_command", pulumi.Output.all(app.name, resource_group.name).apply(lambda args: f"az webapp deploy --resource-group {args[1]} --name {args[0]} --src-path app.py --type zip"))
pulumi.export("blob_url", signed_blob_url)

# Log the web app URL to the info column
app.default_host_name.apply(lambda url: pulumi.log.info(f"Web App URL: http://{url}"))