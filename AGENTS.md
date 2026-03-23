# Geo Extension - Agent Notes

## Project Overview
A Frappe app that enhances the Address doctype with guided, hierarchical address input using autocomplete fields for State, City, and County based on country-specific geographic data.

## Current Architecture

### Core Components
1. **`install.py`** - Property setter setup
   - Changes `state`, `city`, `county` to Autocomplete fieldtype
   - **Moves Country field immediately after `address_type`** (fieldtype remains Link)
   - Reorders fields dynamically per country's administrative hierarchy
   - **NEVER hides any native fields** - all fields remain visible

2. **`locations.py`** - Backend API
   - `get_levels()` - Returns hierarchy configuration from manifest
   - `get_level_options()` - Returns filtered options for each level
   - Good sanitization: `_clean_text()`, `_clean_code()`, `_safe_join()`
   - Uses NFKD normalization for accent-insensitive sorting

3. **`address.js`** - Client-side logic
   - Two modes: "guided" (manifest exists) and "freeform" (no manifest)
   - **Dynamic field labels** update to show country-specific terms (e.g., "Province", "Bundesland")
   - **NEVER hides fields** - all Address fields remain visible always
   - Cascading autocomplete with label→code mapping
   - Rebuilds suggestions without clearing existing values on refresh
   - LEVEL_FIELDS = ["state", "city", "county"]

4. **Data Structure**
   ```
   setup/data/countries/<code>/
   ├── manifest.json      # Hierarchy definition
   ├── level1.csv         # code,name
   ├── level2.csv         # parent_code,code,name
   └── level3.csv         # parent_code,code,name
   ```

## Country Support Status

### ✅ Implemented Countries

| Country | Code | Levels | Hierarchy | Notes |
|---------|------|--------|-----------|-------|
| **Philippines** | ph | 3 | Province → City → Barangay | Uses state, city, county |
| **India** | in | 2 | State → City | Uses state, city |
| **United States** | us | 2 | State → City | Uses state, city |
| **United Kingdom** | gb | 2 | County → City | Uses county, city |
| **Germany** | de | 2 | Bundesland → City | Uses state, city |
| **Singapore** | sg | 1 | Planning Area | Uses city only |
| **Indonesia** | id | 2 | Province → City/Regency | Uses state, city |

### Field Mapping by Country

**Philippines:**
- state → Province
- city → City/Municipality  
- county → Barangay

**India:**
- state → State/Province
- city → City/Town

**United States:**
- state → State
- city → City

**United Kingdom:**
- county → County/Region
- city → City/Town

**Germany:**
- state → Bundesland
- city → City

**Singapore:**
- city → Planning Area

**Indonesia:**
- state → Province
- city → City/Regency

## Key Requirements & Status

### 1. ✅ No Custom Fields
**Status**: Fully implemented
- Uses Property Setters instead of Custom Fields
- Works with standard Address fields only

### 2. ✅ Field Usage Review
**Status**: Reviewed and documented
- Philippines: Uses county for Barangay (may display as "County" in some views)
- UK: Uses county field for UK counties
- Singapore: Single level only

**Note**: Field labels dynamically update in the form to show country-specific terms.

### 3. ✅ Dynamic Field Arrangement
**Status**: Implemented
- Country field now appears immediately after `address_type`
- Country field remains a **Link** field (not Autocomplete)
- Field labels update to match country hierarchy terms
- **ALL native fields remain visible** - nothing is hidden
- Users can manually input in any field regardless of country selection

### 4. ✅ Architecture Improvements
**Completed**:
- Dynamic field label updates in JS
- Better field ordering in install.py

**Potential Future Improvements**:
- Add validation for target_field values in manifest
- Consider virtual fields for better display in standard views

### 5. ✅ Expand Country Support
**Status**: 5 new countries added
- United States (us)
- United Kingdom (gb)
- Germany (de)
- Singapore (sg)
- Indonesia (id)

## Enhancement Tasks - Completed ✅

### Phase 1: Field Arrangement ✅
- [x] Move Country field after address_type
- [x] Create field order system per country
- [x] Test with Philippines and India hierarchies
- [x] Add dynamic field label updates

### Phase 2: Architecture Cleanup ✅
- [x] Document field mapping strategy
- [x] Update JS to handle variable field orders

### Phase 3: Country Expansion ✅
- [x] Add US states and cities (50 states + DC + territories)
- [x] Add UK counties (England, Scotland, Wales, NI)
- [x] Add German states (16 Bundesländer)
- [x] Add Singapore planning areas (53 areas)
- [x] Add Indonesia provinces (34 provinces)

### Phase 4: Testing
- [ ] Test address creation flow
- [ ] Verify field visibility per country
- [ ] Test cascading filters
- [ ] Verify display in Contacts/Customers/Suppliers

## Proposed Next Countries
If expanding further, consider:
1. **Australia (au)** - States → Cities
2. **Canada (ca)** - Provinces → Cities
3. **France (fr)** - Regions → Departments → Cities
4. **Japan (jp)** - Prefectures → Cities
5. **Brazil (br)** - States → Cities
6. **Nigeria (ng)** - States → LGAs
7. **Kenya (ke)** - Counties → Cities
8. **South Africa (za)** - Provinces → Cities
9. **UAE (ae)** - Emirates → Cities
10. **Thailand (th)** - Provinces → Cities

## Code Review Notes

### hooks.py
- ✅ Clean, minimal configuration
- ✅ `doctype_js` correctly points to address.js
- ✅ `after_migrate` calls install setup

### install.py
- ✅ Good docstrings
- ✅ Safe field existence checks
- ✅ New: setup_country_field_position() moves country field

### locations.py
- ✅ Excellent input sanitization
- ✅ Path traversal protection
- ✅ Graceful error handling
- ✅ Unicode normalization for sorting

### address.js
- ✅ Clean separation of guided/freeform modes
- ✅ Preserves values on refresh
- ✅ Good async/await usage
- ✅ NEW: Dynamic field label updates
- ✅ NEW: arrange_fields() for country-specific ordering

## File Changes Summary

### Modified Files:
1. `geo_extension/install.py` - Added country field repositioning
2. `geo_extension/public/js/address.js` - Added dynamic field arrangement
3. `AGENTS.md` - Created documentation

### New Country Data:
- `setup/data/countries/us/` - United States
- `setup/data/countries/gb/` - United Kingdom
- `setup/data/countries/de/` - Germany
- `setup/data/countries/sg/` - Singapore
- `setup/data/countries/id/` - Indonesia

## Development Environment
- Bench: `~/frappe-bench/15/`
- Site: `geo-extension.dev.local`
- App Path: `~/frappe-bench/15/apps/geo_extension/`

## Testing Commands
```bash
# Clear cache after changes
bench --site geo-extension.dev.local clear-cache

# Restart bench
bench restart

# Check app installation
bench --site geo-extension.dev.local list-apps

# Test API
bench --site geo-extension.dev.local execute geo_extension.geo_extension.locations.get_levels --args="['United States']"

# Check property setters
bench --site geo-extension.dev.local mariadb -e "SELECT field_name, property, value FROM \`tabProperty Setter\` WHERE doc_type='Address'"
```

## Migration Notes
The install.py changes require a migrate to apply:
```bash
cd ~/frappe-bench/15
bench --site geo-extension.dev.local migrate
```

This will:
1. Set country fieldtype to Autocomplete
2. Move country field after address_type
3. Set state, city, county to Autocomplete
4. Update field order
