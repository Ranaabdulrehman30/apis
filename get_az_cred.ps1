# 1. Log in to Azure
az login

# 2. Get the current Subscription ID
$SUBSCRIPTION_ID = az account show --query id --output tsv
Write-Host "Using Subscription ID: $SUBSCRIPTION_ID"

# 3. Create a Service Principal with Contributor role
$SP_CREDENTIALS = az ad sp create-for-rbac --name "github-deploy" --role contributor --scopes "/subscriptions/$SUBSCRIPTION_ID" --sdk-auth

# 4. Output credentials (Copy and save this in GitHub Secrets as AZURE_CREDENTIALS)
Write-Host "`nSave the following JSON in GitHub Secrets (AZURE_CREDENTIALS):"
Write-Host $SP_CREDENTIALS
