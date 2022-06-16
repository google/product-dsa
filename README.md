# Product DSAs

*This is not an officially supported Google product.*

## 1. Introduction
Product DSAs is a solution that enables clients to automatically create Dynamic Search Ads (DSAs) for products in their GMC feed and adds an image extension of the product to the ad.
Generated ads are always kept up to date with product availability in stock.

Product DSA can generate two types of campaigns:
- Product level campaign
  - Generate ads for individual products
- Category level campaigns
  - Generate ads for logical groupings of products. Ex: brand, category, color, best sellers…

## 2. Prerequisites
- A Google Cloud Project (GCP), with no apps deployed on AppEngine
- GMC feed with at least 1 unused custom label
- Access to
  - Google Merchant Center
  - Google Ads Account
  - Owner permissions to GCP

## 3. Installation
1. Select products
   - Product level campaign (1000-2000 products)
   - Category level campaigns
2. Add a custom label in the GMC feed for each product in step 1
3. Install the app on GCP
4. Open Product DSA
5. Grant access to newly created service account on GMC
6. Run setup
7. Configure the settings
8. Run the wizard to generate and download:
   - Page-feed
   - Ad customizers feed
   - Campaigns CSV zip file

### Choose Products & Add Custom Labels
Products that will be included in the generated campaigns need to be marked by a custom label.  
** Note: Any custom label can be used - from custom_label_0 to custom_label_4.

##### Product-level Campaigns
- Ads for individual products; an ad group is created for each product.
- For each selected product, add a custom label PDSA_Product
##### Category-level Campaigns
- Categories refer to a logical grouping.
  - Ex: Brand, category, color, best-sellers…
- Each ad targets several products that belong to the same “group”
- Each group has a custom label representing it, that starts with PDSA_Category_
  - Ex: PDSA_Category_Brand, PDSA_Category_Apparel, PDSA_Category_BestSellers…
- For each selected product, add a custom label that represents the group it belongs to starting with PDSA_Category_<group_name>

### Install the app on GCP
1. Open your GCP Project
2. Click on the Cloud Shell icon at the top right
3. In the shell:
```
git clone https://github.com/google/product-dsa.git
cd product-dsa
./install.sh
```
4. In the pop-up window press “Authorise”
5. Wait for the deployment to complete

### Open Product DSA
1. Go to AppEngine > Dashboard
2. Click on the app link at the top right
