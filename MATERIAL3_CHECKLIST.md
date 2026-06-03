# Material 3 UI/UX Compliance Checklist / Чек-лист соответствия стандартам Material 3

This document serves as the mandatory checklist for verifying that all UI/UX components in the Face Recognition Service comply with the Material 3 design system (https://m3.material.io/). Any new features, layout changes, or component updates MUST be validated against this checklist.

Этот документ является обязательным чек-листом для проверки соответствия всех компонентов UI/UX стандарту Material 3 (https://m3.material.io/). Любые новые функции, изменения макета или обновления компонентов ДОЛЖНЫ быть проверены по этому списку.

---

## 1. Color Palette & Roles / Цветовая палитра и роли

| Role / Роль | Description & Check / Описание и проверка |
| :--- | :--- |
| **Primary & Container** | Use for key action buttons (e.g., Search, Import). Contrast must be checked using CSS vars (`--md-sys-color-primary` on `var(--md-sys-color-on-primary)`). |
| **Secondary & Tertiary** | Use for chips, badges, and secondary actions. Female actors are colored with secondary container, male with primary container to align with semantic roles. |
| **Surface Containers** | M3 introduces lowest, low, normal, high, and highest surface colors. Ensure background lists use `surface-container-low` (like results/cards) and outer panels use `surface`. |
| **Contrast Ratio** | Text-to-background contrast ratio must be at least **4.5:1** for regular text and **3:1** for large text. Checked in dark and light modes. |

**Verification Steps / Шаги проверки:**
- [ ] Toggle theme (Dark / Light) and verify that all labels are readable.
- [ ] Verify that no hardcoded hex codes are used in component files; all colors must reference CSS variables or tailwind tokens mapping to variables (e.g. `bg-surface-container`).

---

## 2. Shapes & Borders / Формы и скругления

Material 3 uses pronounced rounded corners (shapes) to define container boundaries:

| Shape Size | Radius | Typical Use Cases / Применение | Compliant / Соответствует |
| :--- | :--- | :--- | :--- |
| **Extra Small** | `4px` | Scrollbars | `rounded-xs` |
| **Small** | `8px` | Small action buttons, image cards, tooltips | `rounded-sm` / `rounded-md` |
| **Medium** | `12px` | Buttons, text inputs, dropdowns | `rounded-lg` / `rounded-button` / `rounded-field` |
| **Large** | `16px` | Detail modals, comparison cards | `rounded-xl` / `rounded-card` |
| **Extra Large** | `24px` | Action cards, grid panels | `rounded-2xl` |
| **Full / Pill** | `9999px` | Filter chips, state indicators | `rounded-chip` / `rounded-full` |

**Verification Steps / Шаги проверки:**
- [ ] Actor thumbnails must use `rounded-2xl` for smooth, modern corners.
- [ ] Inputs and selects must use `rounded-field` (`rounded-xl` / `rounded-lg`).
- [ ] Modals/Sheets must use `rounded-[28px]` or `rounded-xl` for larger containers.

---

## 3. Layout, Alignment & Sizing / Сетка, выравнивание и размеры

| Checkpoint / Точка проверки | Specification / Спецификация | Status / Статус |
| :--- | :--- | :--- |
| **Touch Targets** | All interactive elements (buttons, selects, tabs) must have a minimum interactive area of **44x44px** (or **48x48px** per M3 specs). | Checked / Проверено |
| **Height Alignment** | Input fields, selects, and adjacent action buttons must align perfectly at the bottom using `items-end` and share matching heights (e.g., standard 36px, 40px, or 48px). | Checked / Проверено |
| **Responsive Grid** | Layout must fluidly adapt from 1 column (mobile) to 2 columns (tablet) and 3 columns (large desktop). | Checked / Проверено |
| **Thumbnail Scale** | Facial crops must scale to matching sizes dynamically (e.g., list=60px, modal=80px, comparison=150px) without distortion, using dynamic scale styles. | Checked / Проверено |

**Verification Steps / Шаги проверки:**
- [ ] Verify that adjacent inputs and buttons (e.g. StashDB search box or image count selector) do not look crooked. Use flex-layout with matching vertical dimensions.
- [ ] Crop boxes and face thumbnails must render at visible pixel sizes; check that no classes like `h-15 w-15` (non-existent in default Tailwind) are used.

---

## 4. Interaction & States / Взаимодействие и состояния

All interactive components must have distinct states defined in `index.css`:

1. **Hover State**: Layer opacity `var(--md-sys-state-hover-opacity)` (8%).
2. **Focus State**: Visible outline ring utilizing `var(--md-sys-color-focus-ring)`.
3. **Pressed State**: Layer opacity `var(--md-sys-state-pressed-opacity)` (12%).
4. **Disabled State**: Opacity reduced to `38%` (`disabled:opacity-50` or equivalent).

**Verification Steps / Шаги проверки:**
- [ ] Focus ring must appear when navigating via keyboard Tab key.
- [ ] Hover and click state layers must feel snappy but smooth, utilizing standard ease timings: `var(--md-sys-motion-duration-short)` (120ms).
