---
description: Start interactive crawler development workflow - explore site with DevTools, document paths, then build and test crawler
---

# Crawler Development Workflow

You are now in **crawler development mode**. This is a collaborative workflow to build a working crawler.

## Phase 1: Exploratory (You + User)

### Your Role
- Use Chrome DevTools MCP tools to navigate the target site
- Ask user where to go, what to click, what data to extract
- Record EVERY step in a crawl path document

### Start by asking:
1. What site/page are we crawling?
2. Is Chrome already open with DevTools? (needs `--remote-debugging-port=9222`)
3. What data do you want to extract?

### During Exploration
Use these DevTools MCP tools:
- `mcp__chrome-devtools__navigate_page` - Go to URLs
- `mcp__chrome-devtools__take_snapshot` - See page structure (use this frequently!)
- `mcp__chrome-devtools__click` - Click elements
- `mcp__chrome-devtools__fill` - Fill forms
- `mcp__chrome-devtools__wait_for` - Wait for elements
- `mcp__chrome-devtools__take_screenshot` - Visual confirmation

### Recording Path
Create/update a file called `crawl-path.md` in current directory. For EVERY action, record:

```markdown
## Step N: [Action Description]
- Action: navigate / click / fill / wait / extract
- Target: [element description]
- CSS Selector: `[selector]`
- JS Selector: `document.querySelector('[selector]')`
- Notes: [any special handling needed]
```

For data extraction, record:
```markdown
## Data: [Field Name]
- Location: [where on page]
- CSS Selector: `[selector]`
- Type: text / number / date / list
- Example value: [what you see]
```

### Key Questions to Ask User
- "I see [elements]. Which one should I click?"
- "Found [data]. Is this what you want to extract?"
- "Should I wait for anything after this action?"
- "What's the next step from here?"

## Phase 2: Build (Subagent)

When user says exploration is complete:

1. Confirm the crawl-path.md is complete
2. Ask user: "Python/Playwright or JavaScript?"
3. Launch the `crawler-builder` agent with Task tool:

```
Use Task tool with subagent_type="crawler-builder" and prompt:
"Build a crawler based on crawl-path.md in [current directory].
Language: [Python/JS].
Output file: [filename].
Read the crawl-path.md first, then implement each step."
```

## Phase 3: Test (Subagent)

After builder completes:

Launch the `crawler-tester` agent:
```
Use Task tool with subagent_type="crawler-tester" and prompt:
"Test the crawler at [crawler file path].
Expected output format is in crawl-path.md.
Run the crawler and validate results.
If tests fail, report what needs fixing."
```

### Iteration Loop
If tester reports failures:
1. Share failure details with user
2. Ask if they want to re-explore or just fix code
3. Re-run builder with fix instructions
4. Re-run tester
5. Repeat until pass

## Completion Checklist
- [ ] crawl-path.md documents all steps
- [ ] Crawler script created
- [ ] Crawler tested and working
- [ ] Output format validated

---

**START NOW**: Ask the user what site they want to crawl and confirm DevTools MCP is ready.
