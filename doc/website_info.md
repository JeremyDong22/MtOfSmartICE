# Meituan Merchant Backend (美团商家后台) - Website Information

## Overview

- **Website Name**: 美团管家 (Meituan Guanjia / Meituan Manager)
- **Platform**: Meituan POS System (Point of Sale)
- **Base URL**: `https://pos.meituan.com/`
- **Login Portal**: `https://ecom.meituan.com/bizaccount/login.html` or `https://eepassport.meituan.com/portal/login`

## Authentication

- **Login Method**: SMS Code Verification (Phone Number)
- **SSO Endpoint**: `https://rmslogin.meituan.com/api/v1/login/sso/validateAndRefresh`
- **Token Management**: `https://eepassport.meituan.com/gw/epassport/settoken`

## Main Pages

### Store Selection Page
- **URL**: `https://pos.meituan.com/web/rms-account#/selectorg`
- **Purpose**: Select which restaurant/store to manage
- **Features**:
  - Search by organization name/code
  - Filter by city
  - List of available stores with merchant IDs

## Registered Stores (As of Current Session)

| Store Name | Merchant ID | Organization Code |
|------------|-------------|-------------------|
| 宁桂杏山野烤肉（绵阳1958店） | 56756952 | MD00006 |
| 宁桂杏山野烤肉（常熟世贸店） | 56728236 | MD00007 |
| 野百灵·贵州酸汤火锅（1958店） | 56799302 | MD00008 |
| 宁桂杏山野烤肉（上马店） | 58188193 | MD00009 |
| 野百灵·贵州酸汤火锅（德阳店） | 58121229 | MD00010 |
| 宁桂杏山野烤肉（江油首店） | 58325928 | MD00011 |

## Technical Stack

- **Frontend Framework**: Vue.js based SPA (Single Page Application)
- **API Version**: v1
- **Security**:
  - CSRF protection via `mtgsig` parameter
  - Device fingerprinting (`dfpId`)
  - Yoda security SDK (version 4.1.1)

## Related Domains

| Domain | Purpose |
|--------|---------|
| `pos.meituan.com` | Main POS application |
| `ecom.meituan.com` | E-commerce / Business account |
| `eepassport.meituan.com` | Enterprise passport / SSO |
| `rmslogin.meituan.com` | RMS (Restaurant Management System) Login |
| `portal-portm.meituan.com` | Portal modules and security |
| `s3plus.meituan.net` | Static assets (CDN) |
| `catfront.dianping.com` | Analytics / Logging |
| `plx.meituan.com` | Tracking / Analytics |
| `verify.meituan.com` | Verification services |

## Notes

- The system uses a unified login across multiple Meituan merchant services
- Session cookies are shared across subdomains
- Mobile phone verification is required for login
