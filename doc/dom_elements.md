# Meituan Merchant Backend - DOM Elements & Crawling Reference

## Store Selection Page (`#/selectorg`)

### Page Structure

```
RootWebArea "美团管家"
├── Header
│   └── Logo (image): https://s3plus.meituan.net/mpack/rms-portal/logo-black_*.svg
├── Main Content
│   ├── Title: "请选择要登录的集团/门店"
│   ├── Search Section
│   │   ├── Search Input (textbox)
│   │   ├── Search Button
│   │   └── City Filter (combobox)
│   └── Store List
│       └── Store Cards (repeating)
│           ├── Store Type Badge ("门店")
│           ├── Store Name
│           ├── Merchant ID ("商户号")
│           ├── Organization Code ("机构编码")
│           └── Select Button ("选 择")
```

### Key CSS Selectors

#### Search Elements
```css
/* Search input field */
input[placeholder="请输入机构名称/编码"]

/* Search button */
button[aria-label="search"]
/* or via image */
button img[alt="search"]

/* City dropdown */
[role="combobox"][aria-autocomplete="list"]
```

#### Store List Elements
```css
/* Store card container - based on structure pattern */
.store-card  /* (class name may vary, inspect actual DOM) */

/* Store name text */
/* Pattern: Contains store name like "宁桂杏山野烤肉" */

/* Select button for each store */
button:contains("选 择")
/* or by StaticText content */
```

### XPath Selectors

```xpath
# Search input
//input[@placeholder="请输入机构名称/编码"]

# Search button
//button[.//img[@alt="search"]]

# All store select buttons
//button[contains(text(), "选 择")]

# Store names (by merchant ID pattern)
//*[contains(text(), "商户号")]/preceding-sibling::*

# Specific store by merchant ID
//*[contains(text(), "56756952")]/ancestor::*[contains(@class, "store")]//button
```

### Accessibility Tree UIDs (from Snapshot)

| Element | UID | Description |
|---------|-----|-------------|
| Search Input | `uid=1_17` | textbox "请输入机构名称/编码" |
| Search Button | `uid=1_21` | button "search" |
| City Dropdown | `uid=1_31` | combobox (expandable) |
| Store 1 Select | `uid=1_60` | button "选 择" (绵阳1958店) |
| Store 2 Select | `uid=1_82` | button "选 择" (常熟世贸店) |
| Store 3 Select | `uid=1_104` | button "选 择" (1958店火锅) |
| Store 4 Select | `uid=1_126` | button "选 择" (上马店) |
| Store 5 Select | `uid=1_148` | button "选 择" (德阳店) |
| Store 6 Select | `uid=1_170` | button "选 择" (江油首店) |

---

## API Endpoints for Crawling

### Authentication APIs

```
POST https://eepassport.meituan.com/gw/login/sendSmsCode
- Send SMS verification code

POST https://eepassport.meituan.com/gw/login/mobile
- Login with mobile phone + SMS code

POST https://rmslogin.meituan.com/api/v1/login/sso/validateAndRefresh
- Validate and refresh SSO token

POST https://eepassport.meituan.com/gw/epassport/settoken
- Set authentication token
```

### Store/Organization APIs

```
GET https://pos.meituan.com/web/api/v1/permissions/accounts/myself
- Get current user account info

POST https://pos.meituan.com/web/api/v1/admin/h5/login/v3
- H5 login endpoint (version 3)

POST https://pos.meituan.com/web/api/v1/admin/query-login-poi-geo-info
- Query store geographic information
```

### Security Headers Required

All API requests require:
```
Query Parameters:
- yodaReady=h5
- csecplatform=4
- csecversion=4.1.1
- mtgsig={signature_object}  (for sensitive operations)
```

### mtgsig Structure
```json
{
  "a1": "1.2",           // Version
  "a2": 1765653674477,   // Timestamp
  "a3": "dfpId",         // Device fingerprint
  "a5": "encrypted...",  // Encrypted data
  "a6": "signature...",  // Signature
  "a8": "hash...",       // Hash
  "a9": "4.1.1,7,108",   // SDK version info
  "a10": "39",           // Platform code
  "x0": 4,               // Platform type
  "d1": "hash..."        // Device hash
}
```

---

## JavaScript Files & Resources

### Main Application Bundle
- Hosted on: `s3plus.meituan.net`
- Pattern: `/mss_*/` paths for static assets

### Security SDK
```
Portal Module: https://portal-portm.meituan.com/horn/v1/modules/H5guard_BaseSec/prod
Tracking Module: https://portal-portm.meituan.com/horn/v1/modules/H5guardTrack/prod
```

### Analytics/Logging
```
https://catfront.dianping.com/api/pv    - Page view
https://catfront.dianping.com/api/log   - Logs
https://catfront.dianping.com/batch     - Batch events
https://plx.meituan.com/                - Tracking pixels
https://lx1.meituan.net/                - Additional tracking
```

---

## Cookie Information

Key cookies (inspect browser for actual values):
- Session cookies on `*.meituan.com` domain
- SSO tokens shared across subdomains
- Device fingerprint cookies

---

## Crawling Strategy Notes

1. **Authentication**: Must handle SMS verification - cannot be fully automated without manual intervention or API access
2. **Session Management**: Maintain cookies across requests
3. **Rate Limiting**: Be mindful of request frequency to avoid blocks
4. **Security Signatures**: `mtgsig` parameter generation may require reverse engineering the Yoda SDK
5. **Store Selection**: After login, must select a specific store before accessing store-specific data

## Page Navigation Flow

```
Login Page → SMS Verification → Store Selection → Dashboard
                                      ↓
                               (Select Store)
                                      ↓
                              Store Dashboard
```
