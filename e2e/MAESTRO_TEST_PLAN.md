# Plan: Write real, comprehensive Maestro E2E tests

## Context

Current tests only navigate to screens and take screenshots — they don't test actual features. Need to rewrite all 15 flows to perform real interactions and verify real outcomes.

## Prerequisites (fix before tests)

1. **Add missing testIDs to preferences-sheet.tsx** — testIDs on `<Text>` don't work, must go on parent `<View>` wrappers
2. **Add testIDs to save-record-modal buttons** — save/revisar button, line dropdown
3. **All container Views must have `accessible={false}`** for child testIDs to be visible

## Seed data reminder

Available after `e2e/setup.sh`:
- Line "250 Ecologica" (APPROVED, route near -17.394/-66.182, active detour reason="construction")
- Line "120 UMSS" (APPROVED, ~3km away)
- Line "Test Pending" (PENDING, near test location)
- 3 trip sessions on Line 250, device_id="test-device"
- Transit graph rebuilt

## The 15 flows — what each MUST do

### Explore tab (6 flows)

**1. explore-nearby-lines.yaml** — Verify nearby lines discovery
```
- Launch app, set location
- Assert "Líneas cercanas" section visible
- Assert "250 Ecologica" line card visible (within 2km)
- Tap the line card
- Assert line detail map view appears (header shows "Línea 250 Ecologica")
- Take screenshot of line detail
```

**2. explore-nearby-radius-filter.yaml** — Test radius filtering
```
- Launch app, set location
- Assert nearby lines section visible
- Tap radius header to expand
- Assert radius buttons visible (500m, 1km, 2km, 5km)
- Tap "5km" button
- Wait for reload
- Assert "120 UMSS" now visible (3km away, appears at 5km)
- Tap "500m" button
- Wait for reload
- Take screenshot (fewer or no lines at 500m)
```

**3. explore-search-route.yaml** — Full route search flow
```
- Launch app, set location
- Tap origin input, erase default text
- Type "Mercado 25 de Mayo" (known Cochabamba location)
- Wait for suggestions, tap first one
- Tap destination input
- Type "Universidad Mayor" (another known location)
- Wait for suggestions, tap first one
- Tap search button
- Wait for results (may take several seconds)
- Assert "Rutas disponibles" visible
- Take screenshot of results
```

**4. explore-detour-alert.yaml** — Verify detour badge on nearby line
```
- Launch app, set location
- Assert nearby lines section visible
- Assert "Desvío" text visible (detour badge on Line 250)
- Tap on Line 250 card
- Assert detour banner visible ("Desvío por construction" or similar)
- Take screenshot of line detail with detour
```

**5. explore-preferences-pending.yaml** — Toggle pending lines preference
```
- Launch app, set location
- Assert "Test Pending" NOT visible in nearby lines
- Tap preferences gear
- Wait for bottom sheet
- Assert "Preferencias" title visible
- Tap the pending lines toggle switch
- Swipe down to close sheet (or tap outside)
- Wait for nearby lines to reload
- Assert "Test Pending" NOW visible
- Take screenshot
```

**6. explore-preferences-compare.yaml** — Compare search with/without pending
```
- Launch app, set location
- Tap preferences gear
- Assert preferences sheet visible
- Take screenshot showing toggles
- Close preferences
- Take screenshot of explore screen
```

### Record tab (3 flows)

**7. record-trip.yaml** — Record a normal trip
```
- Launch app, set location
- Tap "Trazar" tab
- Assert "Desliza para empezar" visible
- Swipe right on the switch area (bottom of screen)
- Wait 5 seconds (recording in progress)
- Assert recording indicator visible (duration counter or "Grabando")
- Swipe left on the switch area (stop recording)
- Assert save modal appears ("Guardar recorrido" visible)
- Tap line dropdown to expand
- Tap "250 Ecologica" from the list
- Tap "Guardar" button
- Take screenshot after save
```

**8. record-detour.yaml** — Record and flag as detour
```
- Launch app, set location
- Tap "Trazar" tab
- Swipe right to start recording
- Wait 5 seconds
- Swipe left to stop
- Assert save modal visible
- Tap line dropdown, select "250 Ecologica"
- Scroll down to find "Es un desvío" toggle
- Tap the detour toggle
- Assert reason buttons appear ("Construcción", "Protesta", etc.)
- Tap "Construcción"
- Tap "Revisar desvío" button
- Assert confirmation screen ("Confirmar desvío" visible)
- Assert map is shown
- Take screenshot of confirmation
```

**9. record-cancel.yaml** — Discard a recording
```
- Launch app, set location
- Tap "Trazar" tab
- Swipe right to start
- Wait 3 seconds
- Swipe left to stop
- Assert save modal visible
- Tap "Descartar"
- Assert back on record screen ("Desliza para empezar" visible again)
- Take screenshot
```

### Contribute tab (2 flows)

**10. contribute-vote-route.yaml** — Vote on route accuracy
```
- Launch app, set location
- Tap "Contribuir" tab
- Wait for content to load
- Assert "¿Estas rutas son correctas?" visible (if pending routes exist)
- OR assert "No hay rutas pendientes" (empty state)
- Take screenshot
```

**11. contribute-vote-line.yaml** — Vote on line familiarity
```
- Launch app, set location
- Tap "Contribuir" tab
- Wait for content
- Assert "¿Conoces estas líneas?" visible (if nearby unfamiliar lines exist)
- OR assert empty state
- Take screenshot
```

### Detour lifecycle (1 flow)

**12. detour-confidence-decay.yaml** — Verify detour is visible with confidence info
```
- Launch app, set location
- Assert nearby lines section visible
- Assert "Desvío" text visible on Line 250
- Assert "construction" or detour reason text visible
- Take screenshot showing detour badge with confidence
```

### Favorites tab (3 flows)

**13. favorites-view-saved.yaml** — View empty favorites
```
- Launch app
- Tap "Favoritos" tab
- Assert "No tienes rutas guardadas" visible (empty state on fresh app)
- Take screenshot
```

**14. favorites-save-and-view.yaml** — Save route then view in favorites
```
- Launch app, set location
- Search for a route (origin → destination)
- From results, tap a route
- Tap "Guardar" button
- Tap "Viaje recurrente" in the alert
- Tap "Favoritos" tab
- Assert "Recurrentes" section visible
- Take screenshot showing saved trip
```

**15. favorites-delete.yaml** — Delete a saved trip
```
- Launch app
- Tap "Favoritos" tab
- If trips exist: tap trash icon, confirm deletion
- Take screenshot
```

## Additional testIDs needed

Add to `preferences-sheet.tsx`:
- Wrap "Preferencias" title Text in `<View testID="prefs-title">`
- Wrap "Incluir líneas pendientes" in `<View testID="prefs-pending-lines">`
- Add `testID="prefs-pending-lines-switch"` to the Switch component
- Add `testID="prefs-pending-routes-switch"` to the second Switch

Add to `save-record-modal.tsx`:
- `testID="modal-line-dropdown"` on the dropdown Pressable
- `testID="modal-save-btn"` on the save/revisar button

Add to `explore.tsx`:
- `testID="explore-line-card-{name}"` on each nearby line Pressable (dynamic)

## Maestro interaction patterns

**Tap by testID:** `tapOn: { id: "explore-search-btn" }`
**Tap by text:** `tapOn: "250 Ecologica"` (for dynamic content)
**Tab navigation:** `tapOn: "Trazar, tab.*"` (regex on accessibility label)
**Swipe recording switch:** `swipe: { direction: "RIGHT", startX: "20%", endX: "80%", startY: "88%", endY: "88%" }`
**Type in focused input:** `inputText: "Mercado"`
**Clear text:** `eraseText: 30`
**Wait:** `waitForAnimationToEnd` (use 2-3 times for longer waits)
**Assert visible:** `assertVisible: "text"` or `assertVisible: { id: "testID" }`
**Assert NOT visible:** `assertNotVisible: "text"`
**Screenshot:** `takeScreenshot: "name"`
**Hide keyboard:** `hideKeyboard`

## Files to modify

| File | Change |
|------|--------|
| `app/components/preferences-sheet.tsx` | Wrap texts in Views with testIDs, add testID to Switches |
| `app/components/save-record-modal.tsx` | Add testID to dropdown and save button |
| `app/app/(tabs)/explore.tsx` | Add testID to nearby line cards |
| `e2e/flows/*.yaml` | Rewrite all 15 flows with real interactions |

## Verification

Run individual flow: `maestro test e2e/flows/explore-nearby-lines.yaml`
Run all flows: `maestro test e2e/flows/`
Full suite with server: `./e2e/run-tests.sh`
