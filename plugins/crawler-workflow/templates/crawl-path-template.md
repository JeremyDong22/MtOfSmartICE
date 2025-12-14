# Crawl Path: [Site Name]

> Generated during exploratory phase
> Date: [YYYY-MM-DD]

## Overview
- **Target URL**: [starting URL]
- **Purpose**: [what data to extract]
- **Auth Required**: Yes / No

---

## Navigation Steps

### Step 1: [Action Name]
- **Action**: navigate / click / fill / wait / hover
- **Target**: [description of element]
- **CSS Selector**: `[selector]`
- **JS Selector**: `document.querySelector('[selector]')`
- **Wait After**: [ms or element to wait for]
- **Notes**: [special handling]

### Step 2: [Action Name]
- **Action**:
- **Target**:
- **CSS Selector**: ``
- **JS Selector**: ``
- **Wait After**:
- **Notes**:

<!-- Add more steps as needed -->

---

## Data Extraction

### Field: [Field Name]
- **Location**: [where on page]
- **CSS Selector**: `[selector]`
- **JS Selector**: `document.querySelector('[selector]').textContent`
- **Type**: text / number / date / boolean
- **Example Value**: [actual value seen]
- **Transform**: [any parsing needed, e.g., "remove $ prefix"]

### Field: [Field Name]
- **Location**:
- **CSS Selector**: ``
- **Type**:
- **Example Value**:

---

## List/Table Extraction (if applicable)

### Table: [Table Name]
- **Container**: `[table selector]`
- **Row Selector**: `[row selector]`
- **Pagination**: [how to get next page, or "none"]

| Field | Selector (within row) | Type | Example |
|-------|----------------------|------|---------|
| [field1] | `[selector]` | text | [example] |
| [field2] | `[selector]` | number | [example] |

---

## Expected Output Format

```json
{
  "field1": "example value",
  "field2": 123,
  "items": [
    {
      "subfield1": "value",
      "subfield2": 456
    }
  ]
}
```

---

## Special Handling

### Iframes
- [ ] Site uses iframes
- Frame selector: `[if applicable]`

### Dynamic Content
- [ ] Content loads dynamically
- Wait strategy: [what to wait for]

### Popups/Modals
- [ ] Site shows popups
- Dismiss selector: `[selector to close]`

### Authentication
- [ ] Requires login
- Login preserved via: CDP session / cookies

---

## Notes
[Any additional observations during exploration]
