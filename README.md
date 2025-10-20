<div align="center">
  <a href="https://frappe.io/products/drive">
    <img src=".github/new_logo.svg" height="80" width="80" alt="Frappe Drive Logo">
  </a>
  <h2>Geo Extension</h2>

**Enhancing the Address Experience in Frappe**
</div>

## Geo Extension

Geo Extension is a lightweight Frappe app that enhances the default Geo module by improving how users encode and manage address information. It extends the Address Doctype to make primary address keys (like State, City, and County) filterable and interactive — turning tedious address input into a smooth, guided process.

With country-specific manifests and hierarchical data levels, users can select from real administrative divisions instead of typing free-form text, drastically reducing data entry errors.

### Motivation

Encoding addresses in ERPNext or any Frappe app can be repetitive and error-prone — especially for data-heavy workflows like customer registration, delivery setup, or supplier profiling.
I built Geo Extension to simplify this process by making address encoding filtered, intuitive, and contextual.

This project was also a personal challenge: to build something useful and shareable with the Frappe Community, demonstrating how modular extensions can improve user experience within the framework.

### Key Features

- Dynamic Address Hierarchy. Automatically adapts field labels and filters (e.g., Province → City → Barangay) based on the selected country’s configuration.
- Manifest-Driven Location Levels. Country-specific manifest.json files define how address hierarchies load and map to Frappe fields.
- Autocomplete Field Enhancement. Converts static Data fields like state, city, and barangay into Autocomplete fields for faster, error-free entry.
- Flexible Fallback Behavior. If no manifest exists for the selected country, the app gracefully falls back to standard Data input — keeping the form usable by default.
- Reference Data Support. Supports location datasets in CSV format with hierarchical linkage across levels (Province → City → Barangay).
- Seamless Integration. Works directly with the existing Frappe Address Doctype — no new doctypes or dependencies required.


<details>
<summary>More screenshots</summary>

![Image Preview](https://github.com/user-attachments/assets/993cbd87-a96c-4e5c-8737-0c03c9222723)

![File Sharing Dialog](https://github.com/user-attachments/assets/acb1a542-53d1-4d0e-b2e2-6c9b87f04e69)

![Editor](https://github.com/user-attachments/assets/fe87dfd1-3f55-42df-94b9-f7baed03a391)

![Editor with real time editing](https://github.com/user-attachments/assets/f89a2fab-e618-4d7d-90a6-aaa2cf45fa55)

</details>

### Supported Countries

🇵🇭 Philippines

Want to add your country? See how to contribute below.


## Production setup

### Managed Hosting
You can try [Frappe Cloud](https://frappecloud.com), a simple, user-friendly and sophisticated [open-source](https://github.com/frappe/press) platform to host Frappe applications with peace of mind.

It takes care of installation, setup, upgrades, monitoring, maintenance and support of your Frappe deployments. It is a fully featured developer platform with an ability to manage and control multiple Frappe deployments.

<div>
	<a href="https://frappecloud.com/dashboard/signup?product=geo_extension" target="_blank">
		<picture>
			<source media="(prefers-color-scheme: dark)" srcset="https://frappe.io/files/try-on-fc-white.png">
			<img src="https://frappe.io/files/try-on-fc-black.png" alt="Try on Frappe Cloud" height="28" />
		</picture>
	</a>
</div>

### Self Hosting

Follow these steps to set up Geo Extension in production:

**Step 1**: Download the easy install script

```bash
wget https://frappe.io/easy-install.py
```

**Step 2**: Run the deployment command

```bash
python3 ./easy-install.py deploy \
    --project=geo_extension_prod_setup \
    --email=your_email.example.com \
    --image=ghcr.io/sudopotito/geo_extension \
    --version=stable \
    --app=geo_extension \
    --sitename subdomain.domain.tld
```

Replace the following parameters with your values:
- `your_email.example.com`: Your email address
- `subdomain.domain.tld`: Your domain name where Geo Extension will be hosted

The script will set up a production-ready instance of Geo Extension with all the necessary configurations in about 5 minutes.


## Development Setup

### Docker

You need Docker, docker-compose and git setup on your machine. Refer [Docker documentation](https://docs.docker.com/). After that, follow below steps:

**Step 1**: Setup folder and download the required files

    mkdir geo_extension
    cd geo_extension

    # Download the docker-compose file
    wget -O docker-compose.yml https://raw.githubusercontent.com/sudopotito/geo_extension/develop/docker/docker-compose.yml

    # Download the setup script
    wget -O init.sh https://raw.githubusercontent.com/sudopotito/geo_extension/develop/docker/init.sh

**Step 2**: Run the container and daemonize it

    docker compose up -d

**Step 3**: The site [http://geo_extension.localhost:8000](http://geo_extension.localhost:8000) should now be available. The default credentials are:
- Username: Administrator
- Password: admin

### Local

To setup the repository locally follow the steps mentioned below:

1. Install bench and setup a `frappe-bench` directory by following the [Installation Steps](https://frappeframework.com/docs/user/en/installation)
2. Start the server by running 
```bash
bench start
```
3. In a separate terminal window, create a new site by running 
```bash
bench new-site geo_extension.localhost
```
4. Map your site to localhost with the command 
```bash
bench --site geo_extension.localhost add-to-hosts
```
5. Download the app. Run 
```bash
bench get-app https://github.com/sudopotito/geo_extension
```
6. Install the app on the site 
```bash
bench --site geo_extension.localhost install-app geo_extension
```
7. Now open the URL `http://geo_extension.localhost:8000` in your browser, you should see the app running

## Contribute

We welcome contributions from the community!
If your country is not yet supported, you can easily help extend the list.

Here’s how:

Fork the repository.

Create a new folder in geo_extension/geo_extension/locations/data/<country_code>

Add your country’s location data as CSV files (level1.csv, level2.csv, level3.csv, etc.)

Create a manifest.json describing the hierarchy and mapping to Frappe fields.

Include metadata like:

author, version, description, source

Submit a pull request and briefly describe your country’s hierarchy (e.g., Province → City → District).

Your contribution helps users around the world encode addresses accurately and intuitively — and makes the Frappe ecosystem even more global.

### Community

Contributions, suggestions, and discussions are always welcome.
Feel free to fork, explore, or share improvements that make address data entry even more intuitive.


### License
This project is open-sourced under the MIT License.