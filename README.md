
Check the  [![Github Repo](https://img.shields.io/badge/Github-Repo-blue)](https://github.com/pulumi/examples/tree/master/azure-py-appservice) which I took inspiration of


# Azure App Service with SQL Database and Application Insights - Adapted for CLCO A3 exercise by Matthias Huber

Starting point for building web application hosted in Azure App Service.

Provisions Azure SQL Database and Azure Application Insights to be used in combination
with App Service.

## Running the App

1. Create a new stack:

    ```bash
    $ pulumi stack init dev
    ```

1. Login to Azure CLI (you will be prompted to do this during deployment if you forget this step):

    ```bash
    $ az login
    ```

1. Create a Python virtualenv, activate it, and install dependencies:

    This installs the dependent packages [needed](https://www.pulumi.com/docs/intro/concepts/how-pulumi-works/) for our Pulumi program.

    ```bash
    $ python3 -m venv venv
    $ .\.venv\Scripts\Activate  (Windows only)
    $ pip3 install -r requirements.txt
    ```

1. Specify the Azure location to use:

    ```bash
    $ pulumi config set azure-native:location uksouth
    ```

1. Define SQL Server password (make it complex enough to satisfy Azure policy):

    ```bash
    $ pulumi config set --secret sqlPassword GanzGeheim123!
    ```

1. Run `pulumi up` to preview and deploy changes:

    ``` bash
    $ pulumi up
    Previewing changes:
    ...

    Performing changes:
    ...
    info: 10 changes performed:
        + 10 resources created
    Update duration: 1m14.59910109s
    ```

1. Check the deployed website endpoint:

    ```bash
    $ pulumi stack output endpoint
    https://azpulumi-as0ef47193.azurewebsites.net
    $ curl "$(pulumi stack output endpoint)"
    <html>
        <body>
            <h1>Greetings from Azure App Service!</h1>
        </body>
    </html>
    ```
1. Get the endpoint:

    ```bash
    $ pulumi stack output endpoint
    https://azpulumi-as0ef47193.azurewebsites.net
    $ curl "$(pulumi stack output endpoint)"
    <html>
        <body>
            <h1>Greetings from Azure App Service!</h1>
        </body>
    </html>
    ```
   
1. If pulumi is messed up:
   ```bash
    $ pulumi cancel
    ```

## Found issues

https://learn.microsoft.com/en-us/azure/app-service/deploy-run-package 

### Refactored Deployment Approach

#### Original Implementation
The original file used `asset.AssetArchive` to package and deploy the application as a ZIP file:

```python
source=asset.AssetArchive({"app.py": asset.FileAsset("app.py")})
```

#### Adapted Implementation
The adapted file directly uses `asset.FileAsset` to upload `app.py` without zipping:

```python
source=asset.FileAsset("app.py")
```

This also turned out not to work, as the `app.py` file was not found in the deployment package.

So I changed the approach and used the deployment via direct index.html and without flask.
