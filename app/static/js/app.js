const FEELINGS = [
  ["great", "Great"],
  ["good", "Good"],
  ["okay", "Okay"],
  ["low", "Low"],
  ["rough", "Rough"],
];

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const WEEKDAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const state = {
  people: [],
  personId: null,
  tab: "calendar",
  date: "",
  day: null,
  marks: {},
  progress: null,
  admin: null,
  sheet: null,
  confirm: null,
  error: "",
  notice: "",
  busy: false,
  scrollPending: false,
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function feelingLabel(value) {
  const match = FEELINGS.find((item) => item[0] === value);
  return match ? match[1] : "";
}

function kindLabel(value) {
  if (value === "weights") return "Weights";
  if (value === "cardio") return "Cardio";
  return value;
}

function isoFromParts(year, monthIndex, day) {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function isoFromDate(date) {
  return isoFromParts(date.getFullYear(), date.getMonth(), date.getDate());
}

function todayISO() {
  return isoFromDate(new Date());
}

function parseISODate(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return date;
}

function shiftDay(iso, delta) {
  const date = parseISODate(iso) || new Date();
  date.setDate(date.getDate() + delta);
  return isoFromDate(date);
}

function shiftMonth(iso, delta) {
  const date = parseISODate(iso) || new Date();
  const target = new Date(date.getFullYear(), date.getMonth() + delta, 1);
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  return isoFromParts(target.getFullYear(), target.getMonth(), Math.min(date.getDate(), last));
}

function monthCells(anchor) {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const start = new Date(first);
  start.setDate(1 - first.getDay());
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    cells.push(day);
  }
  return cells;
}

function shortDate(iso) {
  const date = parseISODate(iso);
  if (!date) return iso;
  return `${WEEKDAYS_SHORT[date.getDay()]}, ${MONTHS[date.getMonth()].slice(0, 3)} ${date.getDate()}`;
}

function longDate(iso) {
  const date = parseISODate(iso);
  if (!date) return iso;
  return `${WEEKDAYS[date.getDay()]}, ${MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

function monthTitle(iso) {
  const date = parseISODate(iso);
  if (!date) return "";
  return `${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

function me() {
  return state.people.find((person) => person.id === state.personId) || null;
}

function setPerson(id) {
  state.personId = id;
  localStorage.setItem("healthPersonId", String(id));
}

function clearPerson() {
  state.personId = null;
  state.day = null;
  localStorage.removeItem("healthPersonId");
}

function isAdmin() {
  return location.pathname === "/admin" || location.pathname === "/admin/";
}

function dayPath() {
  return `/api/days/${state.personId}/${state.date}`;
}

async function api(path, options = {}) {
  const opts = { method: options.method || "GET", headers: {} };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout || 12000);
  opts.signal = controller.signal;
  if (options.body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(path, opts);
  } catch (err) {
    throw new Error("That didn't go through. Try again.");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    let detail = "Something went wrong.";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
      if (Array.isArray(detail)) {
        detail = detail.map((item) => item.msg || "").filter(Boolean).join(" ");
      }
    } catch (err) {
      detail = "Something went wrong.";
    }
    throw new Error(typeof detail === "string" ? detail : "Something went wrong.");
  }
  if (response.status === 204) return null;
  return response.json();
}

function setBusy(on) {
  state.busy = on;
  document.body.classList.toggle("busy", on);
}

function showNotice(message) {
  state.notice = message;
  state.error = "";
  let banner = document.querySelector("#app .banner.good");
  document.querySelectorAll("#app .banner.bad").forEach((node) => node.remove());
  if (!banner) {
    banner = document.createElement("p");
    banner.className = "banner good";
    const top = document.querySelector("#app .top");
    if (top) top.insertAdjacentElement("afterend", banner);
    else document.getElementById("app").prepend(banner);
  }
  banner.textContent = message;
}

function showError(message) {
  state.error = message;
  state.notice = "";
  document.querySelectorAll("#app .banner.good").forEach((node) => node.remove());
  let banner = document.querySelector("#app .banner.bad");
  if (!banner) {
    banner = document.createElement("p");
    banner.className = "banner bad";
    banner.setAttribute("role", "alert");
    const top = document.querySelector("#app .top");
    if (top) top.insertAdjacentElement("afterend", banner);
    else document.getElementById("app").prepend(banner);
  }
  banner.textContent = message;
}

function clearBanners() {
  state.error = "";
  state.notice = "";
  document.querySelectorAll("#app .banner").forEach((node) => node.remove());
}

function storedScalars(overrides = {}) {
  const day = state.day || {};
  return {
    feeling: day.feeling || "",
    notes: day.notes || "",
    weight_lb: day.weight_lb ?? null,
    systolic: day.systolic ?? null,
    diastolic: day.diastolic ?? null,
    pulse: day.pulse ?? null,
    water_glasses: day.water_glasses ?? null,
    ...overrides,
  };
}

function notesValue() {
  const notes = document.querySelector("#app [name=notes]");
  return notes ? notes.value : (state.day && state.day.notes) || "";
}

function readNumber(data, name) {
  const raw = String(data.get(name) ?? "").trim();
  if (!raw) return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error("Use numbers for weight and blood pressure.");
  return value;
}

function readWhole(data, name, label) {
  const value = readNumber(data, name);
  if (value == null) return null;
  if (!Number.isInteger(value)) throw new Error(`${label} should be a whole number.`);
  return value;
}

function glassLabel(count) {
  const glasses = Number(count) || 0;
  return glasses === 1 ? "1 glass" : `${glasses} glasses`;
}

function statusText(day) {
  if (!day || !day.id) return "";
  const parts = [];
  const meals = (day.meals || []).filter((meal) => meal.protein || meal.side).length;
  if (meals) parts.push(`${meals} of 6 meals`);
  const minutes = (day.workouts || []).reduce((sum, item) => sum + Number(item.minutes || 0), 0);
  if (minutes) parts.push(`${minutes} min`);
  if (day.weight_lb != null) parts.push(`${day.weight_lb} lb`);
  if (day.systolic != null) parts.push(`${day.systolic}/${day.diastolic}`);
  if (day.water_glasses) parts.push(glassLabel(day.water_glasses));
  if (day.feeling) parts.push(feelingLabel(day.feeling));
  if (!parts.length && day.notes) parts.push("Note saved");
  return parts.join(" · ");
}

function remember(day, what) {
  state.day = day;
  const status = document.getElementById("status");
  if (status) status.textContent = statusText(day);
  const intro = document.getElementById("intro");
  if (intro) intro.hidden = Boolean(day.id);
  if (what === "feeling") paintFeelings(day.feeling || "");
  if (what === "water") paintWater(day.water_glasses || 0);
  if (what === "notes" || what === "body") {
    const notes = document.querySelector("#app [name=notes]");
    if (notes && document.activeElement !== notes) notes.value = day.notes || "";
  }
  if (what === "body") {
    const fields = [
      ["weight_lb", day.weight_lb],
      ["systolic", day.systolic],
      ["diastolic", day.diastolic],
      ["pulse", day.pulse],
    ];
    fields.forEach(([name, value]) => {
      const input = document.querySelector(`#app [name="${name}"]`);
      if (input) input.value = value == null ? "" : String(value);
    });
  }
  if (what === "meals") {
    day.meals.forEach((meal) => {
      const row = document.querySelector(`.meal[data-slot="${meal.slot}"]`);
      if (!row) return;
      row.classList.toggle("filled", Boolean(meal.protein || meal.side));
      const protein = row.querySelector("[name^=protein]");
      const side = row.querySelector("[name^=side]");
      if (protein) protein.value = meal.protein;
      if (side) side.value = meal.side;
    });
  }
  if (what === "workouts") {
    const list = document.getElementById("workout-list");
    if (list) list.innerHTML = workoutItems(day);
    const note = document.querySelector("#workout-form [name=notes]");
    if (note) note.value = "";
  }
}

function paintFeelings(feeling) {
  document.querySelectorAll("[data-act=feeling]").forEach((button) => {
    const on = button.dataset.feeling === feeling;
    button.classList.toggle("on", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

function paintWater(count) {
  const shown = Number(count) || 0;
  const value = document.querySelector("[data-water-count]");
  if (value) value.textContent = String(shown);
  const less = document.querySelector("[data-act=water][data-delta='-1']");
  const more = document.querySelector("[data-act=water][data-delta='1']");
  if (less) less.disabled = shown <= 0;
  if (more) more.disabled = shown >= 40;
}

async function load() {
  if (isAdmin()) {
    state.admin = await api("/api/admin/summary");
    state.people = state.admin.people.map((person) => ({ id: person.id, name: person.name }));
    if (state.personId && !state.people.some((person) => person.id === state.personId)) clearPerson();
    return;
  }
  state.people = await api("/api/people");
  if (state.personId && !state.people.some((person) => person.id === state.personId)) clearPerson();
  if (!state.personId) {
    state.day = null;
    state.progress = null;
    return;
  }
  if (state.tab === "today" || state.tab === "calendar") {
    state.day = await api(dayPath());
  }
  if (state.tab === "calendar") {
    const cells = monthCells(parseISODate(state.date) || new Date());
    const start = isoFromDate(cells[0]);
    const end = isoFromDate(cells[cells.length - 1]);
    const calendar = await api(`/api/days?person_id=${state.personId}&start=${start}&end=${end}`);
    state.marks = {};
    calendar.days.forEach((day) => {
      state.marks[day.date] = day;
    });
  }
  if (state.tab === "progress") {
    state.progress = await api(`/api/progress?person_id=${state.personId}&today=${encodeURIComponent(todayISO())}`);
  }
}

async function refresh() {
  try {
    await load();
  } catch (err) {
    state.error = state.error || err.message || "That didn't go through. Try again.";
  }
  paint();
}

async function run(work) {
  if (state.busy) return;
  setBusy(true);
  clearBanners();
  let ok = false;
  try {
    await work();
    ok = true;
  } catch (err) {
    showError(err.message || "Something went wrong.");
  } finally {
    setBusy(false);
  }
  if (ok) await refresh();
}

function header() {
  const person = me();
  const title = person ? `Daily · ${person.name}` : "Daily";
  document.title = title;
  return `<header class="top">
    <button type="button" class="brand" data-act="go-today"><span class="mark" aria-hidden="true"></span> Daily</button>
    <button type="button" class="who" data-act="sheet" data-sheet="people">${esc(person ? person.name : "Who")}</button>
  </header>`;
}

function banners() {
  let html = "";
  if (state.error) html += `<p class="banner bad" role="alert">${esc(state.error)}</p>`;
  if (state.notice) html += `<p class="banner good">${esc(state.notice)}</p>`;
  return html;
}

function renderWelcome() {
  const picks = state.people.map((person) => (
    `<button type="button" class="secondary" data-act="pick-person" data-id="${person.id}">${esc(person.name)}</button>`
  )).join("");
  return `<section class="stack">
    <h1>Daily</h1>
    <p class="lede">A health log for each person. Six small meals, water, movement, and how the day feels. Weight and blood pressure only when you want them.</p>
    ${picks ? `<div class="stack">${picks}</div>` : ""}
    <form class="card stack" data-act="welcome">
      <label class="field">Who is this log for?
        <input name="name" maxlength="40" required autocomplete="name" placeholder="Alex">
      </label>
      <button class="primary" type="submit">${picks ? "Add person" : "Start"}</button>
    </form>
  </section>`;
}

function renderToday() {
  const day = state.day;
  if (!day) {
    return `${header()}${banners()}<p class="muted">This day didn't load.</p><button type="button" class="secondary" data-act="reload">Try again</button>`;
  }
  const feelings = FEELINGS.map(([value, label]) => (
    `<button type="button" data-act="feeling" data-feeling="${value}" aria-pressed="${day.feeling === value ? "true" : "false"}" class="${day.feeling === value ? "on" : ""}">${label}</button>`
  )).join("");
  const meals = day.meals.map((meal) => {
    const filled = meal.protein || meal.side ? " filled" : "";
    return `<div class="meal${filled}" data-slot="${meal.slot}">
      <div class="meal-label">Meal ${meal.slot}</div>
      <div class="pair">
        <label class="field">Protein
          <input name="protein-${meal.slot}" maxlength="80" value="${esc(meal.protein)}" placeholder="eggs, yogurt, chicken" autocomplete="off">
        </label>
        <label class="field">Side
          <input name="side-${meal.slot}" maxlength="80" value="${esc(meal.side)}" placeholder="fruit or vegetable" autocomplete="off">
        </label>
      </div>
    </div>`;
  }).join("");
  const glasses = day.water_glasses || 0;
  const onToday = state.date === todayISO();
  return `${header()}
    ${banners()}
    <div class="daybar">
      <button type="button" data-act="shift-day" data-delta="-1" aria-label="Previous day">‹</button>
      <h1>${esc(shortDate(state.date))}</h1>
      <button type="button" data-act="shift-day" data-delta="1" aria-label="Next day">›</button>
    </div>
    ${onToday ? "" : `<div class="today-link"><button type="button" data-act="go-today">Jump to today</button></div>`}
    <p id="intro" class="lede"${day.id ? " hidden" : ""}>Six small meals, water, a little movement, and how this day feels.</p>
    <p id="status">${esc(statusText(day))}</p>
    <div class="chips" aria-label="Jump to a section">
      <button type="button" class="chip" data-act="jump" data-target="water">Water</button>
      <button type="button" class="chip" data-act="jump" data-target="feeling">Feeling</button>
      <button type="button" class="chip" data-act="jump" data-target="meals">Meals</button>
      <button type="button" class="chip" data-act="jump" data-target="move">Move</button>
      <button type="button" class="chip" data-act="jump" data-target="body">Body</button>
    </div>
    <section class="card stack" id="water">
      <h2>Water</h2>
      <p class="muted">Glasses today. Tap plus for each one.</p>
      <div class="stepper" role="group" aria-label="Glasses of water">
        <button type="button" data-act="water" data-delta="-1" aria-label="One less glass" ${glasses <= 0 ? "disabled" : ""}>−</button>
        <span class="stepper-value" data-water-count>${glasses}</span>
        <button type="button" data-act="water" data-delta="1" aria-label="One more glass" ${glasses >= 40 ? "disabled" : ""}>+</button>
      </div>
    </section>
    <section class="card stack" id="feeling">
      <h2>How the day feels</h2>
      <div class="feels" role="group" aria-label="Feeling">${feelings}</div>
      <form class="stack" data-act="save-notes">
        <label class="field">Note
          <textarea id="notes" name="notes" maxlength="2000" placeholder="Sleep, energy, anything that stood out.">${esc(day.notes)}</textarea>
        </label>
        <button class="secondary" type="submit">Save note</button>
      </form>
    </section>
    <section class="card stack" id="meals">
      <h2>Meals</h2>
      <p class="muted">Six small meals. Each one is a protein and a whole-food side.</p>
      <form class="stack" data-act="save-meals">
        ${meals}
        <button class="primary" type="submit">Save meals</button>
      </form>
    </section>
    <section class="card stack" id="move">
      <h2>Movement</h2>
      <p class="muted">Thirty-minute sessions. Cardio, weights, or both.</p>
      <div id="workout-list">${workoutItems(day)}</div>
      <form id="workout-form" class="stack" data-act="add-workout">
        <label class="field">Kind
          <select name="kind">
            <option value="cardio">Cardio</option>
            <option value="weights">Weights</option>
          </select>
        </label>
        <label class="field">Minutes
          <input name="minutes" inputmode="numeric" value="30" required>
        </label>
        <label class="field">Note
          <input name="notes" maxlength="200" placeholder="Easy walk, or the lift" autocomplete="off">
        </label>
        <button class="primary" type="submit">Add session</button>
      </form>
    </section>
    <section class="card stack" id="body">
      <h2>Weight and blood pressure</h2>
      <p class="muted">Only on the days you want them.</p>
      <form class="stack" data-act="save-body">
        <label class="field">Weight (lb)
          <input name="weight_lb" inputmode="decimal" value="${day.weight_lb == null ? "" : esc(day.weight_lb)}" placeholder="pounds" autocomplete="off">
        </label>
        <div class="pair">
          <label class="field">Top number
            <input name="systolic" inputmode="numeric" value="${day.systolic == null ? "" : esc(day.systolic)}" placeholder="top" autocomplete="off">
          </label>
          <label class="field">Bottom number
            <input name="diastolic" inputmode="numeric" value="${day.diastolic == null ? "" : esc(day.diastolic)}" placeholder="bottom" autocomplete="off">
          </label>
        </div>
        <label class="field">Pulse, if you took it
          <input name="pulse" inputmode="numeric" value="${day.pulse == null ? "" : esc(day.pulse)}" placeholder="optional" autocomplete="off">
        </label>
        <button class="primary" type="submit">Save readings</button>
      </form>
    </section>`;
}

function workoutItems(day) {
  if (!day.workouts.length) return `<p class="empty">No session yet.</p>`;
  return day.workouts.map((workout) => (
    `<div class="rowline">
      <div>
        <strong>${esc(kindLabel(workout.kind))}</strong>
        <span class="muted"> · ${workout.minutes} min</span>
        ${workout.notes ? `<div>${esc(workout.notes)}</div>` : ""}
      </div>
      <button type="button" class="danger" data-act="ask-delete-workout" data-id="${workout.id}">Remove</button>
    </div>`
  )).join("");
}

function dayDots(mark) {
  if (!mark) return `<span class="cal-dots"></span>`;
  const dots = [];
  if (mark.meals) dots.push(`<i class="dot meals"></i>`);
  if (mark.workouts) dots.push(`<i class="dot move"></i>`);
  if (mark.water_glasses) dots.push(`<i class="dot water"></i>`);
  if (mark.weight_lb != null) dots.push(`<i class="dot weight"></i>`);
  if (mark.systolic != null) dots.push(`<i class="dot pressure"></i>`);
  return `<span class="cal-dots">${dots.join("")}</span>`;
}

function dayAria(date, mark) {
  const parts = [`${date.getDate()} ${MONTHS[date.getMonth()]}`];
  if (!mark) return `${parts[0]}, nothing logged`;
  if (mark.meals) parts.push(mark.meals === 1 ? "1 meal" : `${mark.meals} meals`);
  if (mark.workouts) parts.push(mark.workouts === 1 ? "1 workout" : `${mark.workouts} workouts`);
  if (mark.water_glasses) parts.push(glassLabel(mark.water_glasses));
  if (mark.weight_lb != null) parts.push("weight");
  if (mark.systolic != null) parts.push("blood pressure");
  if (mark.feeling) parts.push(mark.feeling);
  return parts.join(", ");
}

function renderCalendar() {
  const selected = parseISODate(state.date) || new Date();
  const cells = monthCells(selected);
  const dow = WEEKDAYS_SHORT.map((name) => `<div class="cal-dow">${name}</div>`).join("");
  const grid = cells.map((day) => {
    const key = isoFromDate(day);
    const mark = state.marks[key];
    const outside = day.getMonth() === selected.getMonth() ? "" : " is-outside";
    const today = key === todayISO() ? " is-today" : "";
    const current = key === state.date ? " is-selected" : "";
    const feel = mark && mark.feeling ? ` feel-${mark.feeling}` : "";
    return `<button type="button" class="cal-day${outside}${today}${current}" data-act="pick-day" data-date="${key}" aria-pressed="${current ? "true" : "false"}" aria-label="${esc(dayAria(day, mark))}"><span class="cal-num${feel}">${day.getDate()}</span>${dayDots(mark)}</button>`;
  }).join("");
  return `${header()}
    ${banners()}
    <section class="stack">
      <div class="cal-toolbar">
        <h1>${esc(monthTitle(state.date))}</h1>
        <div class="cal-nav">
          <button type="button" data-act="shift-month" data-delta="-1">Previous</button>
          <button type="button" data-act="go-today">Today</button>
          <button type="button" data-act="shift-month" data-delta="1">Next</button>
        </div>
      </div>
      <p class="cal-legend">
        <span><i class="dot meals"></i> Meals</span>
        <span><i class="dot move"></i> Movement</span>
        <span><i class="dot water"></i> Water</span>
        <span><i class="dot weight"></i> Weight</span>
        <span><i class="dot pressure"></i> Pressure</span>
      </p>
      <p class="muted cal-note">A date takes on a color when a feeling is saved.</p>
      <div class="cal-grid">${dow}${grid}</div>
      ${renderDayPanel()}
    </section>`;
}

function renderDayPanel() {
  const day = state.day;
  const heading = longDate(state.date);
  if (!day || day.date !== state.date) {
    return `<section class="card day-panel"><h2>${esc(heading)}</h2><p class="muted">This day didn't load.</p></section>`;
  }
  const bits = [];
  day.meals.forEach((meal) => {
    if (!meal.protein && !meal.side) return;
    const food = [meal.protein, meal.side].filter(Boolean).join(" · ");
    bits.push(`<p><span class="muted">Meal ${meal.slot}</span><br><strong>${esc(food)}</strong></p>`);
  });
  day.workouts.forEach((workout) => {
    const note = workout.notes ? ` · ${esc(workout.notes)}` : "";
    bits.push(`<p><span class="muted">${esc(kindLabel(workout.kind))}</span><br><strong>${workout.minutes} min</strong>${note}</p>`);
  });
  if (day.water_glasses) bits.push(`<p><span class="muted">Water</span><br><strong>${esc(glassLabel(day.water_glasses))}</strong></p>`);
  if (day.weight_lb != null) bits.push(`<p><span class="muted">Weight</span><br><strong>${day.weight_lb} lb</strong></p>`);
  if (day.systolic != null) {
    const pulse = day.pulse ? ` · pulse ${day.pulse}` : "";
    bits.push(`<p><span class="muted">Blood pressure</span><br><strong>${day.systolic}/${day.diastolic}</strong>${esc(pulse)}</p>`);
  }
  if (day.feeling || day.notes) {
    const label = day.feeling ? feelingLabel(day.feeling) : "Note";
    bits.push(`<p><span class="muted">${esc(label)}</span>${day.notes ? `<br>${esc(day.notes)}` : ""}</p>`);
  }
  const body = bits.length ? bits.join("") : `<p class="empty">Nothing logged this day.</p>`;
  const verb = state.date === todayISO() ? "Log today" : "Log this day";
  return `<section class="card day-panel">
    <h2>${esc(heading)}</h2>
    ${body}
    <button type="button" class="primary" data-act="log-day">${verb}</button>
  </section>`;
}

function renderProgress() {
  const progress = state.progress;
  if (!progress) {
    return `${header()}${banners()}<p class="muted">Progress didn't load.</p><button type="button" class="secondary" data-act="reload">Try again</button>`;
  }
  const week = progress.week;
  const move = week.cardio_minutes + week.weights_minutes;
  const labels = ["S", "M", "T", "W", "T", "F", "S"];
  const feelings = week.feelings.map((item, index) => {
    const feel = item.feeling ? ` feel-${item.feeling}` : "";
    const on = item.date === todayISO() ? " on" : "";
    const name = item.feeling ? feelingLabel(item.feeling) : "No feeling";
    return `<button type="button" class="feel-day${on}" data-act="open-day" data-date="${item.date}" aria-label="${esc(longDate(item.date))}, ${esc(name)}">
      <span>${labels[index]}</span>
      <strong class="${feel.trim()}">${Number(item.date.slice(-2))}</strong>
      <i class="mini-feel tone-${item.feeling || "none"}"></i>
    </button>`;
  }).join("");
  const weights = progress.weights;
  let weightBlock = `<p class="empty">No weight yet. Add it on a day you step on the scale.</p>`;
  if (weights.length === 1) {
    weightBlock = `<button type="button" class="secondary reading" data-act="open-day" data-date="${weights[0].date}"><strong>${weights[0].weight_lb} lb</strong><br><span class="muted">${esc(shortDate(weights[0].date))}</span></button>`;
  } else if (weights.length > 1) {
    const nums = weights.map((row) => row.weight_lb);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const span = max - min || 1;
    const bars = [...weights].reverse().map((row) => {
      const height = 28 + ((row.weight_lb - min) / span) * 72;
      return `<button type="button" data-act="open-day" data-date="${row.date}" aria-label="${row.weight_lb} pounds on ${esc(shortDate(row.date))}">
        <i style="height:${height}%"></i>
        <small>${esc(String(row.date).slice(5))}</small>
      </button>`;
    }).join("");
    const newest = weights[0];
    const older = weights[1];
    const diff = Math.round((newest.weight_lb - older.weight_lb) * 10) / 10;
    const delta = diff === 0 ? "same as the one before" : diff > 0 ? `up ${diff} from the one before` : `down ${Math.abs(diff)} from the one before`;
    weightBlock = `<p><strong>${newest.weight_lb} lb</strong> <span class="muted">${esc(delta)}</span></p><div class="trend">${bars}</div>`;
  }
  const pressures = progress.pressures.length
    ? progress.pressures.map((row) => {
      const pulse = row.pulse ? ` · pulse ${row.pulse}` : "";
      return `<button type="button" class="secondary reading" data-act="open-day" data-date="${row.date}"><strong>${row.systolic}/${row.diastolic}</strong>${esc(pulse)}<br><span class="muted">${esc(shortDate(row.date))}</span></button>`;
    }).join("")
    : `<p class="empty">No blood pressure yet.</p>`;
  return `${header()}
    ${banners()}
    <h1>Progress</h1>
    <p class="lede">${esc(shortDate(week.start))} – ${esc(shortDate(week.end))}. ${week.days_logged} day${week.days_logged === 1 ? "" : "s"} with something logged.</p>
    <section class="stats">
      <article class="card stat"><b>${week.meals}</b><span>of 42 meals</span></article>
      <article class="card stat"><b>${move}</b><span>move minutes</span></article>
      <article class="card stat"><b>${week.cardio_minutes}</b><span>cardio minutes</span></article>
      <article class="card stat"><b>${week.weights_minutes}</b><span>weights minutes</span></article>
      <article class="card stat"><b>${week.water_glasses || 0}</b><span>glasses of water</span></article>
    </section>
    <section class="card stack">
      <h2>How the week felt</h2>
      <p class="muted">A dot takes the color of that day's feeling. Tap a day to open it.</p>
      <div class="week-feel">${feelings}</div>
    </section>
    <section class="card stack">
      <h2>Weight</h2>
      ${weightBlock}
    </section>
    <section class="card stack">
      <h2>Blood pressure</h2>
      ${pressures}
    </section>`;
}

function renderSheet() {
  if (state.sheet !== "people") return "";
  const picks = state.people.map((person) => (
    `<button type="button" class="secondary" data-act="pick-person" data-id="${person.id}">${esc(person.name)}${person.id === state.personId ? " · this phone" : ""}</button>`
  )).join("");
  const mine = me();
  return `<div class="sheet-back">
    <div class="sheet stack" role="dialog" aria-modal="true" aria-label="People">
      <h2>People</h2>
      <p class="muted">Each person's days stay with their name. This phone remembers who you picked.</p>
      ${picks}
      <form class="stack" data-act="add-person">
        <input name="name" maxlength="40" placeholder="New person" required autocomplete="name">
        <button class="primary" type="submit">Add person</button>
      </form>
      ${mine ? `<form class="stack" data-act="rename">
        <input name="name" maxlength="40" value="${esc(mine.name)}" required>
        <button class="secondary" type="submit">Rename ${esc(mine.name)}</button>
      </form>
      <button type="button" class="danger" data-act="ask-delete-person" data-id="${mine.id}" data-name="${esc(mine.name)}">Remove ${esc(mine.name)}</button>` : ""}
      <a class="linkish" href="/admin">Admin</a>
      <button type="button" class="secondary" data-act="close-sheet">Close</button>
    </div>
  </div>`;
}

function renderConfirm() {
  const ask = state.confirm;
  if (!ask) return "";
  return `<div class="sheet-back">
    <div class="sheet stack confirm" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
      <h2 id="confirm-title">${esc(ask.title)}</h2>
      <p>${esc(ask.body)}</p>
      <button type="button" class="danger" data-act="confirm-yes">${esc(ask.yes)}</button>
      <button type="button" class="secondary" data-act="confirm-no">${esc(ask.no || "Keep it")}</button>
    </div>
  </div>`;
}

function renderAdmin() {
  const info = state.admin;
  const people = info ? info.people.map((person) => (
    `<div class="card stack">
      <strong>${esc(person.name)}</strong>
      <span class="muted">${person.days} day${person.days === 1 ? "" : "s"} logged</span>
      <button type="button" class="danger" data-act="ask-delete-person" data-id="${person.id}" data-name="${esc(person.name)}">Remove ${esc(person.name)}</button>
    </div>`
  )).join("") : "";
  const counts = info ? `${info.people.length} people · ${info.days} days · ${info.meals} meals · ${info.workouts} workouts` : "";
  return `${banners()}
    <section class="stack">
      <h1>Admin</h1>
      <p class="lede">Everything lives in one database. Export it before you replace it. Anyone on your Wi-Fi who opens this page can do that.</p>
      <p class="muted">${esc(counts)}</p>
      <button type="button" class="primary" data-act="export-backup">Export full backup</button>
      <form class="card stack" data-act="import-backup">
        <h2>Import</h2>
        <p>This replaces every person and every day with the file. Type REPLACE to confirm.</p>
        <label class="field">Backup file
          <input id="import-file" name="file" type="file" accept="application/json,.json" required>
        </label>
        <label class="field">Confirmation
          <input id="import-word" name="word" autocomplete="off" placeholder="REPLACE">
        </label>
        <button id="import-go" class="danger" type="submit" disabled>Replace all data</button>
      </form>
      <h2>People</h2>
      <p class="muted">Removing a person deletes their meals, workouts, readings, and notes.</p>
      ${people || `<p class="empty">No one yet.</p>`}
      <a class="linkish" href="/">Back to the log</a>
    </section>`;
}

function paintOverlay() {
  document.getElementById("overlay").innerHTML = renderSheet() + renderConfirm();
}

function paint() {
  const app = document.getElementById("app");
  const nav = document.getElementById("nav");
  document.body.classList.toggle("busy", state.busy);
  if (isAdmin()) {
    nav.hidden = true;
    app.innerHTML = renderAdmin();
    paintOverlay();
    return;
  }
  if (!state.personId) {
    nav.hidden = true;
    document.title = "Daily";
    app.innerHTML = banners() + renderWelcome();
    paintOverlay();
    return;
  }
  nav.hidden = false;
  nav.querySelectorAll("[data-tab]").forEach((button) => {
    const on = button.dataset.tab === state.tab;
    button.classList.toggle("on", on);
    if (on) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const screens = { today: renderToday, calendar: renderCalendar, progress: renderProgress };
  const draw = screens[state.tab] || renderToday;
  app.innerHTML = draw();
  if (state.scrollPending) {
    app.scrollTop = 0;
    state.scrollPending = false;
  }
  paintOverlay();
}

async function go(date, tab) {
  if (state.busy) return;
  if (date) state.date = date;
  if (tab) state.tab = tab;
  state.sheet = null;
  state.confirm = null;
  clearBanners();
  state.scrollPending = true;
  await refresh();
}

async function saveFeeling(feeling) {
  if (state.busy || !state.day) return;
  const previous = state.day.feeling || "";
  const next = previous === feeling ? "" : feeling;
  setBusy(true);
  clearBanners();
  try {
    const saved = await api(dayPath(), {
      method: "PUT",
      body: storedScalars({ feeling: next, notes: notesValue() }),
    });
    remember(saved, "feeling");
    showNotice(saved.feeling ? "Feeling saved." : "Feeling cleared.");
    const notes = document.querySelector("#app [name=notes]");
    if (notes && document.activeElement !== notes) notes.value = saved.notes || "";
  } catch (err) {
    paintFeelings(previous);
    if (state.day) state.day.feeling = previous;
    showError(err.message || "That didn't go through. Try again.");
  } finally {
    setBusy(false);
  }
}

let waterGoal = null;
let waterFlight = false;

async function saveWater(delta) {
  if (!state.day) return;
  if (state.busy && !waterFlight) return;
  const shown = Number(document.querySelector("[data-water-count]")?.textContent) || 0;
  const next = Math.min(40, Math.max(0, shown + delta));
  if (next === shown) return;
  waterGoal = next;
  paintWater(next);
  if (waterFlight) return;
  waterFlight = true;
  setBusy(true);
  clearBanners();
  try {
    while (waterGoal != null) {
      const goal = waterGoal;
      waterGoal = null;
      const saved = await api(dayPath(), {
        method: "PUT",
        body: storedScalars({ water_glasses: goal || null, notes: notesValue() }),
      });
      state.day = saved;
    }
    remember(state.day, "water");
    showNotice(state.day.water_glasses ? "Water saved." : "Water cleared.");
  } catch (err) {
    waterGoal = null;
    paintWater(state.day.water_glasses || 0);
    const status = document.getElementById("status");
    if (status) status.textContent = statusText(state.day);
    showError(err.message || "That didn't go through. Try again.");
  } finally {
    waterFlight = false;
    setBusy(false);
  }
}

async function saveSection(work, what) {
  if (state.busy) return;
  setBusy(true);
  clearBanners();
  try {
    const saved = await work();
    remember(saved, what);
    const savedLabel = {
      notes: "Note saved.",
      meals: "Meals saved.",
      body: "Readings saved.",
      workouts: "Session saved.",
    }[what];
    if (savedLabel) showNotice(savedLabel);
  } catch (err) {
    showError(err.message || "That didn't go through. Try again.");
  } finally {
    setBusy(false);
  }
}

function blankMeals() {
  return [1, 2, 3, 4, 5, 6].map((slot) => ({ slot, protein: "", side: "" }));
}

function readMeals(data) {
  return {
    meals: [1, 2, 3, 4, 5, 6].map((slot) => ({
      slot,
      protein: String(data.get(`protein-${slot}`) || ""),
      side: String(data.get(`side-${slot}`) || ""),
    })),
  };
}

async function onSubmit(act, data) {
  if (act === "welcome" || act === "add-person") {
    const created = await api("/api/people", { method: "POST", body: { name: String(data.get("name") || "") } });
    if (act === "welcome" || !state.personId) setPerson(created.id);
    state.sheet = act === "add-person" ? "people" : null;
    state.notice = act === "add-person" ? `${created.name} is on the tracker.` : "";
    return;
  }
  if (act === "rename") {
    const updated = await api(`/api/people/${state.personId}`, {
      method: "PATCH",
      body: { name: String(data.get("name") || "") },
    });
    setPerson(updated.id);
    state.sheet = null;
    state.notice = `Renamed to ${updated.name}.`;
    return;
  }
  if (act === "save-notes") {
    await saveSection(async () => api(dayPath(), {
      method: "PUT",
      body: storedScalars({ notes: String(data.get("notes") || "") }),
    }), "notes");
    return;
  }
  if (act === "save-meals") {
    await saveSection(async () => api(`${dayPath()}/meals`, { method: "PUT", body: readMeals(data) }), "meals");
    return;
  }
  if (act === "save-body") {
    await saveSection(async () => api(dayPath(), {
      method: "PUT",
      body: storedScalars({
        weight_lb: readNumber(data, "weight_lb"),
        systolic: readWhole(data, "systolic", "The top number"),
        diastolic: readWhole(data, "diastolic", "The bottom number"),
        pulse: readWhole(data, "pulse", "Pulse"),
        notes: notesValue(),
      }),
    }), "body");
    return;
  }
  if (act === "add-workout") {
    const minutes = readWhole(data, "minutes", "Minutes");
    await saveSection(async () => api(`${dayPath()}/workouts`, {
      method: "POST",
      body: {
        kind: String(data.get("kind") || "cardio"),
        minutes: minutes == null ? 30 : minutes,
        notes: String(data.get("notes") || ""),
      },
    }), "workouts");
    return;
  }
  if (act === "import-backup") {
    const file = data.get("file");
    if (!file || !file.text) throw new Error("Choose a backup file.");
    let payload;
    try {
      payload = JSON.parse(await file.text());
    } catch (err) {
      throw new Error("That file isn't JSON.");
    }
    const result = await api("/api/admin/import", { method: "POST", body: payload });
    state.notice = `Restored ${result.people} people and ${result.days} days.`;
  }
}

function askRemove(title, body, yes, act, data) {
  state.confirm = { title, body, yes, act, data, no: "Keep it" };
  state.sheet = null;
  paintOverlay();
}

async function confirmYes() {
  const ask = state.confirm;
  if (!ask) return;
  state.confirm = null;
  if (ask.act === "delete-person") {
    const id = Number(ask.data.id);
    await api(`/api/people/${id}`, { method: "DELETE" });
    if (state.personId === id) clearPerson();
    state.notice = `${ask.data.name} was removed.`;
    await refresh();
    return;
  }
  if (ask.act === "delete-workout") {
    const saved = await api(`/api/workouts/${ask.data.id}`, { method: "DELETE" });
    remember(saved, "workouts");
    paintOverlay();
  }
}

document.addEventListener("click", (event) => {
  if (event.target.classList && event.target.classList.contains("sheet-back")) {
    state.sheet = null;
    state.confirm = null;
    paintOverlay();
    return;
  }
  const tab = event.target.closest("#nav [data-tab]");
  if (tab) {
    go(null, tab.dataset.tab);
    return;
  }
  const button = event.target.closest("[data-act]");
  if (!button) return;
  const act = button.dataset.act;
  if (act === "jump") {
    document.getElementById(button.dataset.target)?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (act === "feeling") {
    saveFeeling(button.dataset.feeling || "");
    return;
  }
  if (act === "water") {
    saveWater(Number(button.dataset.delta));
    return;
  }
  if (act === "sheet") {
    const name = button.dataset.sheet || "";
    state.sheet = state.sheet === name || !name ? null : name;
    state.confirm = null;
    paintOverlay();
    return;
  }
  if (act === "close-sheet" || act === "confirm-no") {
    state.sheet = null;
    state.confirm = null;
    paintOverlay();
    return;
  }
  if (act === "pick-person") {
    setPerson(Number(button.dataset.id));
    state.sheet = null;
    state.scrollPending = true;
    clearBanners();
    refresh();
    return;
  }
  if (act === "shift-day") {
    go(shiftDay(state.date, Number(button.dataset.delta)));
    return;
  }
  if (act === "shift-month") {
    go(shiftMonth(state.date, Number(button.dataset.delta)));
    return;
  }
  if (act === "pick-day") {
    state.date = button.dataset.date;
    state.sheet = null;
    state.confirm = null;
    clearBanners();
    refresh().then(() => {
      document.querySelector(".day-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return;
  }
  if (act === "go-today") {
    go(todayISO(), state.tab === "progress" ? "today" : state.tab);
    return;
  }
  if (act === "log-day") {
    go(state.date, "today");
    return;
  }
  if (act === "open-day") {
    go(button.dataset.date, "today");
    return;
  }
  if (act === "reload") {
    refresh();
    return;
  }
  if (act === "ask-delete-person") {
    askRemove(
      `Remove ${button.dataset.name}?`,
      "Their meals, workouts, weight, blood pressure, and notes are deleted with them.",
      "Remove",
      "delete-person",
      { id: button.dataset.id, name: button.dataset.name },
    );
    return;
  }
  if (act === "ask-delete-workout") {
    askRemove("Remove this session?", "The rest of the day stays.", "Remove", "delete-workout", { id: button.dataset.id });
    return;
  }
  if (act === "confirm-yes") {
    if (state.busy) return;
    setBusy(true);
    clearBanners();
    confirmYes().catch((err) => {
      showError(err.message || "Something went wrong.");
      paintOverlay();
    }).finally(() => setBusy(false));
    return;
  }
  if (act === "export-backup") {
    if (state.busy) return;
    setBusy(true);
    clearBanners();
    api("/api/admin/export").then((payload) => {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "daily-backup.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      state.notice = "Backup downloaded.";
      paint();
    }).catch((err) => {
      showError(err.message || "Something went wrong.");
    }).finally(() => setBusy(false));
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.dataset.act) return;
  event.preventDefault();
  const act = form.dataset.act;
  const data = new FormData(form);
  const pending = onSubmit(act, data);
  if (act === "save-notes" || act === "save-meals" || act === "save-body" || act === "add-workout") {
    pending.catch((err) => showError(err.message || "Something went wrong."));
    return;
  }
  run(() => pending);
});

document.addEventListener("input", (event) => {
  if (event.target.id !== "import-word") return;
  const button = document.getElementById("import-go");
  if (button) button.disabled = event.target.value.trim() !== "REPLACE";
});

state.date = todayISO();
const savedPerson = Number(localStorage.getItem("healthPersonId") || "");
if (savedPerson) state.personId = savedPerson;
document.getElementById("app").innerHTML = `<p class="muted">Loading…</p>`;
refresh();
