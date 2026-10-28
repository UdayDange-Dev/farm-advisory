### Farm Advisory

Farm Advisory and Crop Recommendation Management for ERPNext v16.

The app has two separate calculators, both ported from the Agri Smart HTML
prototypes (`Spray_Schedule_Calculator.html`, `basal-dose-calculator.html`):

| Calculator | DocType | Naming | Print format |
|---|---|---|---|
| Spray Schedule | Spray Schedule | `SPS-.YYYY.-` | Spray Schedule Report (EN / MR / both) |
| Fertilizer Basal Dose | Basal Dose Recommendation | `BDR-.YYYY.-` | Basal Dose Recommendation Report |

Both are on the **Farm Advisory** workspace (`/desk/farm-advisory`) with their
masters and reports.

### Navigation

The module sidebar (`farm_advisory/farm_advisory/sidebar/farm_advisory/`) is kept short:

| Sidebar item | Opens |
|---|---|
| Dashboard | The workspace: number cards, a monthly chart, quick actions, master and report cards |
| Basal Dose | The **Basal Dose page** (`/desk/basal-dose`) |
| Spray Schedule | Spray Schedule list |
| Farmers | Customer list |
| Fertilizer Masters, Spray Masters, Reports, Setup | Collapsible groups |

The **Basal Dose page** (`farm_advisory/farm_advisory/page/basal_dose/`) has:

* Summary figures
* One tab per crop: Pomegranate, Banana, Guava, Mango and Papaya
* Recent recommendations
* The top items of the Fertilizer Requirement Summary

Each tab lists the saved Basal Dose Recommendations that contain that crop. It has search, a date range, a village filter and pages of 20. A recommendation with two crops appears in both tabs. The area, plants and crop cost shown are that crop's own rows. **New Recommendation** starts the form with the tab's crop instead of Mango. `/desk/basal-dose?crop=Banana` opens a given tab.

All page figures come from `basal_dose.py`. It reads through `frappe.get_list`, so a user sees only the records their roles, User Permissions and shares allow. The page reads data and never writes it.

The workspace, sidebar, Basal Dose page, Basal form and the three reports are English only.

### Several crops in one recommendation

One Basal Dose Recommendation (one `BDR-` number, one farmer) can hold several crops:

* Each crop is a `Basal Dose Crop` row with its own `crop_no`, variety, spacing, area and plant count.
* Each fertilizer row carries the `crop_no` of the crop it belongs to.
* Every row is calculated from its own crop's plant count.
* A crop's subtotal is the sum of its own rows.
* The recommendation total is the sum of the crop subtotals.

The **Crops & Fertilizers** tab shows one section per crop:

* The crop's details
* Its own fertilizer table
* A crop subtotal
* Actions: Edit Crop, Load Template, Add Fertilizer, Remove Crop (asks for confirmation and removes only that crop's rows)

Below the crop sections:

* The **Combined Fertilizer Purchase Summary**. It groups the same fertilizer and pack size across crops. Its amounts are a regrouping of the crop amounts and are not added to the total again.
* The **Total Recommendation Cost**.

The printed report follows the same order.

If a saved crop is removed but its fertilizer rows are left behind, saving is refused. The rows are never moved to the crop that takes the removed crop's number.

### Fertilizer templates

A crop's basal template is the **Fertilizer Template** table on its Farm Crop. There is one template per crop.

**Managing templates.** The **Fertilizer Templates** panel at the bottom of the Basal Dose page lists every Basal crop:

* Its fertilizers and status: *Template ready* or *No template*
* A search box and a filter by status

Its **Add Template** button (also in the page's ⋯ menu) opens an editor with a fertilizer table. Each row takes:

* fertilizer
* rate
* rate unit
* package size
* bag price
* contains

The same panel offers **Edit**, **Delete** (with confirmation) and **Create Template**.

**Validation.** Templates are saved through the Farm Crop, so its **write** permission applies (Farm Advisory Manager, System Manager), and so does its validation, also in the standard Farm Crop form:

* The rate must be greater than 0.
* The rate unit must be one of the allowed units.
* The pack size and bag price cannot be negative. A value of 0 uses the fertilizer master's value, so the master must have one.
* The same fertilizer cannot appear twice.
* A newly added fertilizer must be active.

The editor never copies another crop's rows.

**Loading a template.** **Load Template** on a recommendation:

* Asks before replacing fertilizer rows the crop already has.
* For a crop without a template, offers **Create Template** to users who may write Farm Crop, then loads the new template into that crop's section.

Fertilizer Requirement Summary has a **Group by Crop** option, which shows each crop's own fertilizer use. Without it, the report shows the combined purchase totals as before.

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app farm_advisory        # requires erpnext
```

Installing (or `bench migrate`) creates the roles, custom fields and
permissions and seeds the reference master data. Seeding is idempotent and
never overwrites records you have edited.

**PDF / WhatsApp sharing** uses Frappe v16's Chrome PDF generator. On each
server, install Chromium and the libraries and font it needs:

```bash
bench setup-chrome
sudo apt-get install libnss3 libasound2t64 fonts-noto-core   # fonts-noto-core = Marathi (Devanagari)
```

Without `fonts-noto-core`, or another Devanagari font, Marathi text in
server-generated PDFs renders as boxes. Browser printing uses the viewer's own
fonts and is not affected.

### Farmers are ERPNext Customers

There is no Farmer DocType. Each calculator record links to a **Customer**
through `customer`, which stores the Customer's name. The farmer section on
Customer holds first/middle/last name, WhatsApp number, village, taluka,
district, state and PIN code (custom fields prefixed `fa_`).

* Choosing a Customer pre-fills the farmer fields on the calculator.
* **Create Customer** on a calculator creates an Individual Customer from the
  typed details. ERPNext also creates its primary Contact. If a Customer with
  the same mobile number already exists, it is linked instead, so the same
  farmer is not created twice.
* The farmer's name, mobile number and address are copied onto each record,
  so an issued schedule keeps the details it was issued with.

### How calculation works

All arithmetic is in Python:

* `farm_advisory/utils/spray_calc.py`
* `farm_advisory/utils/basal_calc.py`

Each document's `validate()` calls these modules. The forms feel live like the
prototypes: every edit is debounced and sent to a whitelisted preview method
(`farm_advisory.api.preview_spray_schedule` / `preview_basal_dose`). That
method runs the same functions on an unsaved copy and returns the figures and
the report preview. The browser never computes a number itself, so nothing
changes when you press Save.

Ported exactly from the prototypes, and cross-checked against the original
JavaScript on 3,000 random spray cases and 1,500 random basal crops with zero
mismatches:

* **Spray Schedule**
  * Area is converted to sq ft: acre 43,560; guntha 1,089; hectare 107,639.1.
  * Spacing in metres is converted to feet at × 3.28084.
  * Plants = `round(area_sqft / (row × plant))`.
  * Water is per acre, per plant, or a manual total. The defaults are 200 L per acre and 1 L per plant.
  * Tanks = `ceil(water / capacity)`.
  * Product quantity:
    * ml/L and gm/L: dose × water.
    * ppm (mg/L): dose × water / 1000, which gives grams.
  * Amount = quantity / 1000 × rate.
  * Pack suggestion uses 100/250/500 ml-gm and 1/5 L-kg packs. It picks the fewest packs, then the smallest total that covers the need.
  * Crop age and bahar age are in y/m/d plus days, counted to the first spray date (today if there is none).
* **Basal Dose**
  * Area is converted to m²: acre 4,046.856; hectare 10,000; guntha 101.171.
  * Spacing in feet is converted to metres at × 0.3048.
  * Plants = `floor(area_m2 / (row × plant))`.
  * Quantity = gm per plant × plants / 1000. A rate in kg per plant is first multiplied by 1000 to get grams.
  * Bags use one of three rounding options:
    * Round up (full bags)
    * Nearest (like Excel)
    * No rounding
  * Amount = bags × cost per bag.
  * Cost per kg and cost per plant are calculated per row and per crop.
  * The purchase list combines rows by fertilizer + pack size. It is printed when it has two or more lines, as in the prototype.

JavaScript rounding (`Math.round`) and `en-IN` number formatting are
reproduced in `utils/numbers.py`, so reports show the same figures as the
prototypes.

### Master data (seeded from the prototypes)

| Master | Notes |
|---|---|
| Farm Crop | 13 crops, Marathi names, spray/basal flags, default spacing, basal fertilizer template |
| Farm Crop Variety | per crop, spray/basal flags |
| Spray Product | by category, Marathi name, default dose unit, optional ERPNext Item |
| Spray Equipment | HTP Pump 200 L, Blower 400 L, Battery sprayer 16 L |
| Farm Fertilizer | 20 fertilizers with pack kg, contents, price per bag, optional Item |
| Farm Village / Taluka / District / State | English + Marathi |
| Branch (ERPNext) | 4 Agri Smart branches; Marathi name, address, phone added as custom fields |
| Farm Advisory Settings | company name/email/tagline/logo, default branch, report language, bag rounding, customer group, territory |

Mango, Pomegranate and Papaya fertilizer templates are seeded as in the
prototype, including their per-crop pack, contents and price overrides. The
prototype has no Banana or Guava template, so none was invented: those crops
start with an empty row.

### Roles and permissions

| Role | Calculators | Masters | Settings |
|---|---|---|---|
| Farm Advisory Manager | full | full | full |
| Farm Advisor | create, read, write, print, email, export, share (no delete) | read, create | read |
| System Manager | full | full | full |

Advisors also get read/write/create on Customer and read on Branch.

### Sharing and export

* **Print / Download PDF**: the A4 print formats above. The Spray report follows the record's *Language* (English, Marathi, or both). The Basal report is in English, as in the prototype. The Basal form does not show the report: it appears only in print preview, print and PDF.
* **WhatsApp**:
  * Where the browser can share files (most mobile browsers over HTTPS), the PDF goes through the device share sheet.
  * Otherwise the PDF is downloaded and WhatsApp opens with the message text, and the user attaches the file. `wa.me` links cannot carry attachments, and the dialog says so.
* **Excel / CSV** (Basal): UTF-8 with a BOM, so Excel shows Marathi correctly. Columns are the same as the prototype's export.
* **Import Old Calculator File** (Basal, on new records): loads a JSON file saved by the HTML calculator's "Save" button.

### Reports

* **Spray Schedule Register**: filters are date range, customer, taluka, branch and crop.
* **Basal Dose Register**: filters are date range, customer, taluka and crop.
* **Fertilizer Requirement Summary**: total quantity, bags and amount per fertilizer + pack size, across recommendations. Use it for stock planning. Its filters are date range, customer, taluka, crop (only that crop's fertilizer rows count) and fertilizer.

### Deliberate differences from the prototypes

1. **Spray plant count before water.** For water "per plant", the prototype briefly used the previous plant count after an area or spacing change (a one-event lag). Here the plant count is calculated first.
2. **No browser storage.** Records are saved in the database. JSON export was not added, because the records, PDF and CSV cover it. Old files can still be imported.
3. **Branch is ERPNext's Branch DocType**, extended with the Marathi name, address and phone. It is not a separate master.
4. **Basal print** gets the company header (logo, company name).
5. **Marathi names were added to the Guava, Mango and Papaya crop masters.** These crops appear only in the English Basal list.
6. **PIN code** is free text checked as 6 digits. **Mobile / WhatsApp** must be 10 digits; a leading `+91` or `0` is removed.
7. **Template price of 0** means "use the fertilizer master price", the same as the prototype's `||` fallback.

### Open questions for the business

1. **Banana and Guava basal templates**: what fertilizers, rates and prices?
2. **Mango template, BIO POTASH**: its *contains* is "BIO AVAILABLE PHOSPHORUS 10 %". This is kept verbatim but looks like a copy error. What is the correct analysis?
3. **Prices**: should spray rates and fertilizer bag prices come from ERPNext Item Price? Both masters have an optional `item` link ready for this.
4. **Grand Naine / Grand Naine (G9)**: the two prototypes spell the Banana variety differently. Both are kept, flagged for spray and basal respectively. Are they the same variety?
5. **Deleting**: should Farm Advisors be able to delete their own drafts? Currently only Managers can delete.
6. **Basal report in Marathi**: not wanted. The Basal report and the Basal Dose screens stay English only (decided 2026-10-28).

### Development

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app farm_advisory
```

* `farm_advisory/tests/test_calculations.py` tests both calculation engines without a database: units, rounding, pack suggestion and ages.
* `farm_advisory/tests/test_integration.py` tests the rest on a site:
  * Customer creation and de-duplication
  * Save, snapshots and validation
  * Preview matching save
  * Print HTML, WhatsApp text and CSV
  * Old-file import
  * The three reports
  * Farm Advisor permissions
* `farm_advisory/tests/test_basal_dose_page.py` tests the Basal Dose page data:
  * Crop counts and crop-tab filtering
  * Search, dates and paging
  * Input validation
  * Permissions, including a User Permission
  * The report crop and fertilizer filters
  * The form without a print section

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/farm_advisory
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

### License

mit
