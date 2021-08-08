# Product DSAs

## 1. Introduction
>TODO

## 2. Installation

>WIP: please ignore the content

### 2.1 Create/use a Google Cloud Project(GCP) with a billing account

* [How to Creating and Managing Projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
* [How to Create, Modify, or Close Your Billing Account](https://cloud.google.com/billing/docs/how-to/manage-billing-account)

### 2.2 Check the permissions
Make sure the user running the installation has following permissions.

* [Standard Access For GMC](https://support.google.com/merchants/answer/1637190?hl=en)
* [Editor(or Owner) Role in Google Cloud Project](https://cloud.google.com/iam/docs/understanding-roles)


### 2.3 Prepare parameters

* [GCP Project Id](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
* [Google Merchant Center Id](https://support.google.com/merchants/answer/188924?hl=en)

### 2.4 Run install script

#### 2.4.1 Setup parameters
You can either put all parameters into `config.yaml` or pass them as command line arguments.

To get initial structure of config.yaml use a template in install folder: `cp ./config.yaml.template ./config.yaml`:
```
dataset_location: us
project_id: YOUR_GCP_PROJECT_ID
merchant_id: YOUR_GMC_ACCOUNT_ID
```

```
./setup.sh --project_id YOUR_GCP_PROJECT_ID --merchant_id YOUR_GMC_ACCOUNT_ID --dataset_location us
```

Or specify config file explicitly:
```
./setup.sh --config config.MY_PROJECT1.yaml
```
If `--config` is omitted then `config.yaml` will be assumed.

You can use not only local path but also file on GCS:
```
./setup.sh --config gs://MY_BUCKET/config.MY_PROJECT1.yaml
```
but in this case you have to use Application Default Credentials (that means you can't use neither `--service-account-key-file` nor `--client-secrets-file`)


#### 2.4.2 Running from local machine

To run the setup script we'll need to setup authentication
* As a end user - see https://cloud.google.com/docs/authentication/end-user
* As a service account - see https://cloud.google.com/docs/authentication/production


Running as a end user assuming you exported user secrets to `client_secrets.json`:
```shell
./setup.sh --client-secrets-file client_secrets.json
```
Running as a service account assuming you exported the SA's keys to `service_account.json`:
```shell
./setup.sh --service-account-key-file service_account.json
```
you can also setup service account's key via environment variable:
```shell
export GOOGLE_APPLICATION_CREDENTIALS="/home/user/product-dsas/service_account.json"
./setup.sh
```
or via gcloud:
```shell
gcloud auth activate-service-account --key-file=/home/user/product-dsas/service_account.json
./setup.sh
```
You can also run using Application Default Creadentials, just execute in your shell first:
```
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive
```

