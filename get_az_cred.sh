# 1. Log in to Azure
az login

# 2. Get the current Subscription ID
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
echo "Using Subscription ID: $SUBSCRIPTION_ID"

# 3. Create a Service Principal with Contributor role
az ad sp create-for-rbac --name "github-deploy" --role contributor --scopes /subscriptions/$SUBSCRIPTION_ID --sdk-auth
