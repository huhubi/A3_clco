import pulumi
import pulumi_azure_native.insights as insights
import pulumi_azure_native.resources as resource
import pulumi_azure_native.sql as sql
import pulumi_azure_native.storage as storage
import pulumi_azure_native.web as web
from pulumi import Config, Output, export, asset
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

# Create an App Service plan
app_service_plan = web.AppServicePlan(
    "appservice-asp",
    resource_group_name=resource_group.name,
    kind="Linux",
    reserved=True,
    sku=web.SkuDescriptionArgs(
        tier="Free",
        name="F1",
    ))

# Upload the Flask application code to the storage account
app_blob_container = BlobContainer(
    "appservice-container",
    account_name=storage_account.name,
    public_access=PublicAccess.NONE,
    resource_group_name=resource_group.name)

app_blob = storage.Blob(
    "appservice-app",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
    container_name=app_blob_container.name,
    type=storage.BlobType.BLOCK,
    source=asset.AssetArchive({"app.py": asset.FileAsset("app.py")})
    #source=asset.FileAsset("app.py")
    # Instead of AssetArchive, we use FileAsset to upload a single file, since the read should work that way
)

# Use WEBSITE_RUN_FROM_PACKAGE app setting to deploy from a URL
blob_url = Output.concat(
    "https://", storage_account.name, ".blob.core.windows.net/",
    app_blob_container.name, "/",
    app_blob.name
)

# Create Application Insights
app_insights = insights.Component(
    "appservice-ai",
    application_type=insights.ApplicationType.WEB,
    kind="web",
    ingestion_mode="applicationInsights",
    resource_group_name=resource_group.name)

# Create a SQL server
sql_server = sql.Server(
    "appservice-sql",
    resource_group_name=resource_group.name,
    administrator_login=username,
    administrator_login_password=pwd,
    version="12.0")

# Create a SQL database
database = sql.Database(
    "appservice-db",
    resource_group_name=resource_group.name,
    server_name=sql_server.name,
    sku=sql.SkuArgs(
        name="S0",
    ))

# Create a connection string
connection_string = Output.concat(
    "Server=tcp:", sql_server.name, ".database.windows.net;initial ",
    "catalog=", database.name,
    ";user ID=", username,
    ";password=", pwd,
    ";Min Pool Size=0;Max Pool Size=30;Persist Security Info=true;")

# Deploy the Flask application as a web app
app = web.WebApp(
    "appservice-flask",
    resource_group_name=resource_group.name,
    server_farm_id=app_service_plan.id,
    site_config=web.SiteConfigArgs(
        linux_fx_version="PYTHON|3.11",
        app_settings=[
            web.NameValuePairArgs(name="APPINSIGHTS_INSTRUMENTATIONKEY", value=app_insights.instrumentation_key),
            web.NameValuePairArgs(name="APPLICATIONINSIGHTS_CONNECTION_STRING",
                                  value=app_insights.instrumentation_key.apply(
                                      lambda key: "InstrumentationKey=" + key
                                  )),
            web.NameValuePairArgs(name="WEBSITE_RUN_FROM_PACKAGE", value=blob_url),
            web.NameValuePairArgs(name="SCM_DO_BUILD_DURING_DEPLOYMENT", value="true"),
            web.NameValuePairArgs(name="ApplicationInsightsAgent_EXTENSION_VERSION", value="~2")
        ],
        connection_strings=[web.ConnStringInfoArgs(
            name="db",
            type="SQLAzure",
            connection_string=connection_string,
        )]
    )
)

# Export outputs
pulumi.export("web_app_url", pulumi.Output.concat("http://", app.default_host_name))
pulumi.export("scm_web_app_url", pulumi.Output.concat("http://", app.default_host_name.apply(lambda name: name.replace(".azurewebsites.net", ".scm.azurewebsites.net"))))
pulumi.export("log_tail_command", pulumi.Output.all(app.name, resource_group.name).apply(lambda args: f"az webapp log tail --name {args[0]} --resource-group {args[1]}"))
pulumi.export("web_ssh_url", pulumi.Output.concat("https://", app.default_host_name.apply(lambda name: name.replace(".azurewebsites.net", ".scm.azurewebsites.net")), "/webssh/host"))

# Log the web app URL to the info column
app.default_host_name.apply(lambda url: pulumi.log.info(f"Web App URL: http://{url}"))
