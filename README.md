# Product DSAs

## 1. Introduction
>TODO

## 2. Configuration

>TODO: OUTDATED!

There are a bunch of settings that can be specified in your configuration. Some of them can be passed via command line and environment variable.

### The BigQuery dataset location.
|| Name            || Required? || Default || Description || command line || env var ||
| `dataset_location` |  No        | us       |              | `--dataset_location` | `DATASET_LOCATION` |
| `project_id`       |  Yes       | Can be detected from environment | GCP project id | `--project_id` | standard GCP env vars: GCP_PROJECT, GOOGLE_CLOUD_PROJECT, DEVSHELL_PROJECT_ID  |
| `merchant_id`      |  Yes       | - |  GMC account id | `--merchant_id` | `MERCHANT_ID` |

### Product DSAs run settings
* `product_campaign_name` - [optional] Should only be provided if the campaign has already been created
* `category_campaign_name` - [optional] Should only be provided if the campaign has already been created
* `dsa_website` - [required] DSA websire, do not specify protocol (http/https) (e.g. 'example.com')
* `dsa_lang` - DSA languare (default: en)
* `page_feed_name` - DSA page feed name in Google Ads
* `page_feed_spreadsheetid` - Google Spreadsheet docid for page feed, will be generated on installation
* `adcustomizer_feed_name` - ad customizer feed name
* `adcustomizer_spreadsheetid` - Google Spreadsheet docid for ad customizer feed, will be generated on installation
* `page_feed_output_file` - [optional] File name for output CSV file with page feed (default: 'page-feed.csv')
* `campaign_output_file` - [optional] File name for output CSV file with campaign data for Ads Editor (default: 'gae-campaigns.csv')
* `adcustomizer_output_file` - [optional] (default: 'ad-customizer.csv')
* `image_folder` - [optional] folder for downloading images from GMC, if relative and output_folder specified then they will be joined (default: 'images')
* `output_folder` - [optional] output folder path, will be common base path for all outputs (default: 'output')
* `pubsub_topic_dt_finish` - pub/sub topic id for publishing message on GMC Data Transfer completions (default: 'gmc-dt-finish')
* `ad_description_template` - template for ad descriptions using fields from GMC product table, e.g. "{title} (price: {price_value} {price_currency})". If ommited than product descriptions from GMC will be used (but be aware that they can easily exceed the limit of 90 symbols, in such a case they will be truncated)
* `category_ad_descriptions` - dictionary with mapping labels to category descriptions (for adgroups)
* `dt_schedule` - DataTransfer custom schedule (by default, if empty, 'every 24 hours'), syntax - https://cloud.google.com/appengine/docs/flexible/python/scheduling-jobs-with-cron-json#cron_json_The_schedule_format)


## 3. Installation

### 2.1 Create/use a Google Cloud Project(GCP) with a billing account

* [How to Creating and Managing Projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
* [How to Create, Modify, or Close Your Billing Account](https://cloud.google.com/billing/docs/how-to/manage-billing-account)


### 2.2 Check the permissions
Make sure the user running the installation has following permissions.

* [Standard Access For GMC](https://support.google.com/merchants/answer/1637190?hl=en)
* one of the following set or [roles](https://cloud.google.com/iam/docs/understanding-roles) in Google Cloud Project
  * Owner
  * Editor plus the following roles:
    * AppEngine specific [roles](https://cloud.google.com/appengine/docs/standard/python/roles): App Engine Admin (`appengine.appAdmin`) and App Engine Creator (`appengine.appCreator`)
    * IAP Policy Admin (`iap.admin`)
    * Big Query Admin (`bigquery.admin`)
    * Pub/Sub Admin (actually the `pubsub.topics.setIamPolicy` permission is needed)
    * Project IAM Admin (`resourcemanager.projectIamAdmin`)

### 2.3 Clone repository
> NOTE: currently using GoB, in the future it'll be Github

* Go to https://professional-services.googlesource.com/new-password and copy code
* Execute the code in Cloud Shell
* git clone https://professional-services.googlesource.com/solutions/product-dsa


### 2.4 Prepare parameters

* [Google Merchant Center Id](https://support.google.com/merchants/answer/188924?hl=en)
  You can use either MCA (root account) or leave accounts.


### 2.5 Set up

#### 2.5.1 Setup parameters
You can either put all parameters into `config.json` or pass them as command line arguments.

To get initial structure of config.json use a template: `cp ./config.json.template ./config.json`.

Example of config.json
```
dataset_location: us
project_id: YOUR_GCP_PROJECT_ID
merchant_id: YOUR_GMC_ACCOUNT_ID
```
using it you can run `./setup.sh` without any arguments.
Alternately you can supply all parameters via command line arguments:
```
./setup.sh --project_id YOUR_GCP_PROJECT_ID --merchant_id YOUR_GMC_ACCOUNT_ID --dataset_location us
```

You can specify config file explicitly:
```
./setup.sh --config config.MY_PROJECT1.json
```
If `--config` is omitted then `config.json` (i.e. a local file in the current directory) assumed.

You can use not only local path but also file on GCS:
```
./setup.sh --config gs://MY_BUCKET/config.MY_PROJECT1.json
```
but in this case you have to use Application Default Credentials (that means you can't use either `--service-account-key-file` or `--client-secrets-file`)
Inside config file path a macro `$PROJECT_ID` is supported, it's replaced with current GCP project id.
For example, `gs://$PROJECT_ID-pdsa/config.json`. It's used to specify a link to a config file for apps deployed in App Engine (in `app.json`).

#### 2.5.2 Installing components
There are two kind of components that should be installed and initialized:
* Web application in Google App Engine with related services - use `install-web.sh`
* BigQuery data transfer for fetching data from GMC to BigQuery with related services - use `setup.sh`

#### 2.5.3 Installing App Engine application
Run `install-web.sh`.

By default it's assumed that the configuration file is on GCS, it's specified in `app.json`:
```
  CONFIG: gs://$PROJECT_ID-pdsa/config.json
```
The file will be deployed there by `setup.sh` (see next).

The script assumes that you're running within a Google Cloud Organization by a member of that org. If you're running the script outside a Cloud Orginization most likely you'll get an error on step "Creating oauth brand (consent screen) for IAP" (see below). This is due to the use of `gcloud alpha iap oauth-brand` commands - which implicity operate on internal brands. For details see https://cloud.google.com/iap/docs/programmatic-oauth-clients. To workaround the error you'll have to create a OAuth consent screen manually and then enable IAP for App Engine app.

    "create-oauth-client": ERROR: (gcloud.alpha.iap.oauth-brands.list) INVALID_ARGUMENT: Request contains an invalid argument.

To update the web application in the future we'll need to run `update-web.sh`.

#### 2.5.4 Installing Data Transfer
`setup.sh` will create BigQuery data transfer for GMC, sets up pub/sub topics and subscriptions to call the web app (in GAE) on every data ctransfer completion (for feeds updating).

To run `setup.sh` you need to set up authentication.
First you need to create an OAuth client credentials on https://pantheon.corp.google.com/apis/credentials (Create credentials -> OAuth client ID -> Application type = Desktop) and export them into as a client secrets file (e.g. client_secret.json).

After that you either pass the client secrets directly via `--client-secrets-file` arg or use Application Default Credentials (ADC).

to run from a local machine:
```shell
./setup.sh --client-secrets-file client_secret.json
```
to run from Cloud Shell (or via ssh):
```shell
./setup.sh --client-secrets-file client_secret.json --non-interactive
```
to set up ADC:
```shell
gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/bigquery.readonly,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive.file --client-id-file=./client_secrets.json
```

You can use a [service account](https://cloud.google.com/docs/authentication/production) as well. But in that case you have to give your service account access permissions for GMC.
Running as a service account assuming you exported the SA's keys to `service_account.json`:
```shell
./setup.sh --service-account-key-file service_account.json
```
you can also setup service account's key via environment variable:
```shell
export GOOGLE_APPLICATION_CREDENTIALS="/home/user/product-dsas/service_account.json"
./setup.sh
```


As soon as `setup.sh` completed you should have:
* a data transfer in BigQuery scheduled to run daily, you can change schedule via `schedule` parameter in config.json, see [Configuration](#2.-Configuration)
* pub/sub topic (it's name also can be customized via config's `pubsub_topic_dt_finish` parameter). Data Transfer will be publishing message to the topic on each transfer completion
* subscription for the topic to call web app in App Engine (assuming `https://{PROJECT_ID}.ew.r.appspot.com/api/update`)
* two Google Spreadsheets created for page feed and for ad customizer feed, their ids put into the configuration in `page_feed_spreadsheetid` and `adcustomizer_spreadsheetid` parameters respectively. That's because `setup.sh` updates the configuration file (if it was a local file).
* the configuration file is copied to GCS under the same name into a bucket named "{PROJECT_ID}-pdsa"
(that url is used by default by the web app in AppEngine)

With successfull setup.sh completion we should be ready to access and use the web app (deployed by `install-web.sh`). To get its url you can always run `gcloud app browse`, but in general the url will look like https://{PROJECT_ID}.ew.r.appspot.com.