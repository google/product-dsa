# Installation

## Create/use a Google Cloud Project(GCP) with a billing account

* [How to Creating and Managing Projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
* [How to Create, Modify, or Close Your Billing Account](https://cloud.google.com/billing/docs/how-to/manage-billing-account)


## Check the permissions
Make sure your have Admin role in GMC.

Make sure the user running the installation is an Owner in GCP project.

Make sure you have access to this Google Group https://groups.google.com/a/professional-services.goog/g/solutions_product-dsa-readers


## Clone repository

* Go to https://professional-services.googlesource.com/new-password and copy code
* Execute the code in Cloud Shell
* `git clone https://professional-services.googlesource.com/solutions/product-dsa`

If you want to get a non-default branch (for example with a dev or old versions) then:
* `git clone -b v2 https://professional-services.googlesource.com/solutions/product-dsa`

## Prepare parameters

* [Google Merchant Center Id](https://support.google.com/merchants/answer/188924?hl=en)
  You can use either MCA (root account) or child accounts.


## Install GAE application

Run `install.sh`

### Troubleshooting

* (gcloud.app.deploy) NOT_FOUND: Unable to retrieve P4SA: [service-NUMBER@gcp-gae-service.iam.gserviceaccount.com] from GAIA. Could be GAIA propagation delay or request from deleted apps.
Execute: `gcloud app deploy`

* "create-oauth-client": ERROR: (gcloud.alpha.iap.oauth-brands.list) INVALID_ARGUMENT: Request contains an invalid argument.
Reason: your GCP project is outside of a Cloud Organization.
Workaround: You need to create an OAuth consent screent manually and re-enable IAP for the AppEngine app.


## Grant GAE SA permissions in GMC
Grant user `${PROJECT_ID}@appspot.gserviceaccount.com` Standard acceess permissions in GMC.


## Grant other users access
To grant access permissions for additional users one should go to https://console.cloud.google.com/security/iap 
and create principals with "IAP-secured Web App User" role.


## Setup

Open the app (http://${PROJECT_ID}.ew.r.appspot.com) and follow the setup wizard.
