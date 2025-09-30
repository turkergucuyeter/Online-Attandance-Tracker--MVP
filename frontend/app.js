import { t } from './i18n.js';

const API_BASE = localStorage.getItem('attendance.apiBase') || 'http://localhost:8000';

const state = {
  user: null,
  token: null,
  flash: null,
  supervisor: {
    tab: 'teachers',
    teachers: [],
    students: [],
    classes: [],
    courses: [],
    terms: [],
    sessions: [],
    featureFlags: {},
  },
  teacher: {
    classes: [],
    selectedClass: null,
    sessions: [],
    selectedSession: null,
    attendance: [],
  },
  student: {
    courses: [],
    summaries: {},
  },
  notifications: [],
};

const appEl = document.getElementById('app');
const userInfoEl = document.getElementById('user-info');
document.getElementById('year').textContent = new Date().getFullYear();

function setFlash(message, type = 'alert') {
  const id = Date.now();
  state.flash = { message, type, id };
  render();
  if (message) {
    setTimeout(() => {
      if (state.flash && state.flash.id === id) {
        state.flash = null;
        render();
      }
    }, 4000);
  }
}

async function apiRequest(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (response.status === 204) {
    return null;
  }
  const contentType = response.headers.get('Content-Type') || '';
  const data = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || data || 'Beklenmedik hata');
  }
  return data;
}

function persistSession() {
  if (state.token && state.user) {
    localStorage.setItem('attendance.token', state.token);
    localStorage.setItem('attendance.user', JSON.stringify(state.user));
  } else {
    localStorage.removeItem('attendance.token');
    localStorage.removeItem('attendance.user');
  }
}

function restoreSession() {
  const token = localStorage.getItem('attendance.token');
  const userRaw = localStorage.getItem('attendance.user');
  if (token && userRaw) {
    try {
      state.token = token;
      state.user = JSON.parse(userRaw);
    } catch (error) {
      state.token = null;
      state.user = null;
    }
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  const email = formData.get('email');
  const password = formData.get('password');
  try {
    const result = await apiRequest('/auth/login', {
      method: 'POST',
      body: { email, password },
    });
    state.token = result.token;
    state.user = result.user;
    persistSession();
    await loadInitialData();
    render();
  } catch (error) {
    setFlash(error.message, 'alert');
  }
}

function handleLogout() {
  state.token = null;
  state.user = null;
  state.notifications = [];
  persistSession();
  render();
}

async function loadInitialData() {
  if (!state.user) return;
  try {
    state.notifications = await apiRequest('/notifications');
  } catch (error) {
    console.warn('Bildirimler yüklenemedi', error);
  }
  if (state.user.role === 'supervisor') {
    await Promise.all([
      loadSupervisorTeachers(),
      loadSupervisorStudents(),
      loadSupervisorClasses(),
      loadSupervisorCourses(),
      loadSupervisorTerms(),
      loadSupervisorSessions(),
      loadFeatureFlags(),
    ]);
  }
  if (state.user.role === 'teacher') {
    await loadTeacherClasses();
  }
  if (state.user.role === 'student') {
    await loadStudentCourses();
  }
}

async function loadSupervisorTeachers() {
  state.supervisor.teachers = await apiRequest('/supervisor/teachers');
}

async function loadSupervisorStudents() {
  state.supervisor.students = await apiRequest('/supervisor/students');
}

async function loadSupervisorClasses() {
  state.supervisor.classes = await apiRequest('/supervisor/classes');
}

async function loadSupervisorCourses() {
  state.supervisor.courses = await apiRequest('/supervisor/courses');
}

async function loadSupervisorTerms() {
  state.supervisor.terms = await apiRequest('/supervisor/terms');
}

async function loadSupervisorSessions() {
  state.supervisor.sessions = await apiRequest('/supervisor/schedule-sessions');
}

async function loadFeatureFlags() {
  state.supervisor.featureFlags = await apiRequest('/feature-flags');
}

async function loadTeacherClasses() {
  state.teacher.classes = await apiRequest('/teacher/classes');
}

async function loadTeacherSessions(classId) {
  state.teacher.sessions = await apiRequest(`/teacher/classes/${classId}/sessions`);
}

async function loadTeacherAttendance(sessionId) {
  const data = await apiRequest(`/teacher/sessions/${sessionId}/attendance`);
  state.teacher.selectedSession = data.session;
  state.teacher.attendance = data.attendance.map((item) => ({
    student_id: item.student_id,
    student_name: item.student_name,
    status: item.status || 'present',
  }));
}

async function loadStudentCourses() {
  const courses = await apiRequest('/student/courses');
  state.student.courses = courses;
  for (const course of courses) {
    const summary = await apiRequest(`/student/courses/${course.id}/attendance-summary`);
    state.student.summaries[course.id] = summary;
  }
}

function renderFlash() {
  if (!state.flash) return '';
  const cls = state.flash.type === 'success' ? 'alert success' : 'alert';
  return `<div class="${cls}">${state.flash.message}</div>`;
}

function renderLogin() {
  const wrapper = document.createElement('div');
  wrapper.className = 'login-wrapper card';
  wrapper.innerHTML = `
    <h2>${t('auth.loginTitle')}</h2>
    ${renderFlash()}
    <form class="grid">
      <label>
        <span>${t('auth.email')}</span>
        <input name="email" type="email" required placeholder="supervisor@example.com" />
      </label>
      <label>
        <span>${t('auth.password')}</span>
        <input name="password" type="password" required placeholder="Şifre" />
      </label>
      <button class="primary" type="submit">${t('auth.login')}</button>
    </form>
    <div class="card" style="margin-top:1.5rem;background:rgba(37,99,235,0.08);">
      <h3>Demo Kullanıcıları</h3>
      <ul>
        <li>Supervisor: supervisor@example.com / Supervisor123!</li>
        <li>Öğretmen: teacher@example.com / Teacher123!</li>
        <li>Öğrenci: student@example.com / Student123!</li>
      </ul>
    </div>
  `;
  const form = wrapper.querySelector('form');
  form.addEventListener('submit', handleLogin);
  appEl.appendChild(wrapper);
}

function renderSupervisor() {
  const container = document.createElement('div');
  container.className = 'grid';
  container.innerHTML = `
    ${renderFlash()}
    <div class="card">
      <div class="navbar">
        ${['teachers','students','classes','courses','terms','sessions','reports','flags','notifications'].map((tab) => `
          <button data-tab="${tab}" class="${state.supervisor.tab === tab ? 'active' : ''}">
            ${t(`nav.${tab === 'flags' ? 'flags' : tab}`) || tab}
          </button>
        `).join('')}
      </div>
    </div>
    <div class="card" id="supervisor-content"></div>
  `;
  appEl.appendChild(container);
  container.querySelectorAll('button[data-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.supervisor.tab = btn.dataset.tab;
      render();
    });
  });
  renderSupervisorContent();
}

function renderSupervisorContent() {
  const content = document.getElementById('supervisor-content');
  if (!content) return;
  const tab = state.supervisor.tab;
  switch (tab) {
    case 'teachers':
      content.innerHTML = renderTeacherAdmin();
      attachTeacherAdminEvents(content);
      break;
    case 'students':
      content.innerHTML = renderStudentAdmin();
      attachStudentAdminEvents(content);
      break;
    case 'classes':
      content.innerHTML = renderClassAdmin();
      attachClassAdminEvents(content);
      break;
    case 'courses':
      content.innerHTML = renderCourseAdmin();
      attachCourseAdminEvents(content);
      break;
    case 'terms':
      content.innerHTML = renderTermAdmin();
      attachTermAdminEvents(content);
      break;
    case 'sessions':
      content.innerHTML = renderSessionAdmin();
      attachSessionAdminEvents(content);
      break;
    case 'reports':
      content.innerHTML = renderReports();
      attachReportEvents(content);
      break;
    case 'flags':
      content.innerHTML = renderFlags();
      attachFlagEvents(content);
      break;
    case 'notifications':
      content.innerHTML = renderNotifications();
      attachNotificationEvents(content);
      break;
    default:
      content.innerHTML = '';
  }
}

function renderTeacherAdmin() {
  const list = state.supervisor.teachers.map((teacher) => `
    <tr>
      <td>
        <div class="badge">
          <span class="dot" style="background:${teacher.display_color}"></span>
          ${teacher.name}
        </div>
      </td>
      <td>${teacher.email}</td>
      <td>${teacher.is_active ? 'Aktif' : 'Pasif'}</td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.teachers')}</h2>
    <form id="create-teacher" class="grid two">
      <label><span>${t('common.name')}</span><input name="name" required /></label>
      <label><span>${t('common.email')}</span><input name="email" type="email" required /></label>
      <label><span>Şifre</span><input name="password" type="password" placeholder="Opsiyonel" /></label>
      <label><span>${t('common.color')}</span><input name="display_color" type="color" value="#2563eb" /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>${t('common.name')}</th><th>${t('common.email')}</th><th>Durum</th></tr></thead>
      <tbody>${list || '<tr><td colspan="3">Henüz öğretmen yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachTeacherAdminEvents(content) {
  const form = content.querySelector('#create-teacher');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    if (!payload.password) {
      delete payload.password;
    }
    try {
      await apiRequest('/supervisor/teachers', { method: 'POST', body: payload });
      await loadSupervisorTeachers();
      setFlash('Öğretmen oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderStudentAdmin() {
  const list = state.supervisor.students.map((student) => `
    <tr>
      <td>${student.name}</td>
      <td>${student.email}</td>
      <td>${student.student_no}</td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.students')}</h2>
    <form id="create-student" class="grid two">
      <label><span>${t('common.name')}</span><input name="name" required /></label>
      <label><span>${t('common.email')}</span><input name="email" type="email" required /></label>
      <label><span>Öğrenci No</span><input name="student_no" required /></label>
      <label><span>Veli İletişim</span><input name="guardian_contact" /></label>
      <label><span>Şifre</span><input name="password" type="password" placeholder="Opsiyonel" /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>${t('common.name')}</th><th>${t('common.email')}</th><th>Öğrenci No</th></tr></thead>
      <tbody>${list || '<tr><td colspan="3">Henüz öğrenci yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachStudentAdminEvents(content) {
  const form = content.querySelector('#create-student');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    if (!payload.password) delete payload.password;
    try {
      await apiRequest('/supervisor/students', { method: 'POST', body: payload });
      await loadSupervisorStudents();
      setFlash('Öğrenci oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderClassAdmin() {
  const list = state.supervisor.classes.map((cls) => `
    <tr>
      <td>${cls.name}</td>
      <td>${cls.grade}</td>
      <td>${cls.branch}</td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.classes')}</h2>
    <form id="create-class" class="grid two">
      <label><span>${t('common.name')}</span><input name="name" required /></label>
      <label><span>${t('common.grade')}</span><input name="grade" type="number" required /></label>
      <label><span>${t('common.branch')}</span><input name="branch" required /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>${t('common.name')}</th><th>${t('common.grade')}</th><th>${t('common.branch')}</th></tr></thead>
      <tbody>${list || '<tr><td colspan="3">Henüz sınıf yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachClassAdminEvents(content) {
  const form = content.querySelector('#create-class');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.grade = Number(payload.grade);
    try {
      await apiRequest('/supervisor/classes', { method: 'POST', body: payload });
      await loadSupervisorClasses();
      setFlash('Sınıf oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderCourseAdmin() {
  const classOptions = state.supervisor.classes.map((cls) => `<option value="${cls.id}">${cls.name}</option>`).join('');
  const teacherOptions = state.supervisor.teachers.map((teacher) => `<option value="${teacher.id}">${teacher.name}</option>`).join('');
  const list = state.supervisor.courses.map((course) => `
    <tr>
      <td>${course.name}</td>
      <td>${course.code}</td>
      <td>${course.class_name}</td>
      <td><span class="badge"><span class="dot" style="background:${course.display_color}"></span>${course.teacher_name}</span></td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.courses')}</h2>
    <form id="create-course" class="grid two">
      <label><span>${t('common.name')}</span><input name="name" required /></label>
      <label><span>Kod</span><input name="code" required /></label>
      <label><span>Sınıf</span><select name="class_id" required><option value="">Seçiniz</option>${classOptions}</select></label>
      <label><span>Öğretmen</span><select name="teacher_id" required><option value="">Seçiniz</option>${teacherOptions}</select></label>
      <label><span>Haftalık Saat</span><input name="weekly_hours" type="number" min="1" value="1" /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>${t('common.name')}</th><th>Kod</th><th>Sınıf</th><th>Öğretmen</th></tr></thead>
      <tbody>${list || '<tr><td colspan="4">Henüz ders yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachCourseAdminEvents(content) {
  const form = content.querySelector('#create-course');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.class_id = Number(payload.class_id);
    payload.teacher_id = Number(payload.teacher_id);
    payload.weekly_hours = Number(payload.weekly_hours || 1);
    try {
      await apiRequest('/supervisor/courses', { method: 'POST', body: payload });
      await loadSupervisorCourses();
      setFlash('Ders oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderTermAdmin() {
  const list = state.supervisor.terms.map((term) => `
    <tr>
      <td>${term.name}</td>
      <td>${term.start_date}</td>
      <td>${term.end_date}</td>
      <td>${term.absence_threshold_percent}%</td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.terms')}</h2>
    <form id="create-term" class="grid two">
      <label><span>${t('common.name')}</span><input name="name" required /></label>
      <label><span>${t('common.date')} (Başlangıç)</span><input name="start_date" type="date" required /></label>
      <label><span>${t('common.date')} (Bitiş)</span><input name="end_date" type="date" required /></label>
      <label><span>${t('supervisor.threshold')}</span><input name="absence_threshold_percent" type="number" min="0" max="100" value="30" /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>${t('common.name')}</th><th>Başlangıç</th><th>Bitiş</th><th>Eşik</th></tr></thead>
      <tbody>${list || '<tr><td colspan="4">Henüz dönem yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachTermAdminEvents(content) {
  const form = content.querySelector('#create-term');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.absence_threshold_percent = Number(payload.absence_threshold_percent || 30);
    try {
      await apiRequest('/supervisor/terms', { method: 'POST', body: payload });
      await loadSupervisorTerms();
      setFlash('Dönem oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderSessionAdmin() {
  const courseOptions = state.supervisor.courses.map((course) => `<option value="${course.id}">${course.name} (${course.class_name})</option>`).join('');
  const termOptions = state.supervisor.terms.map((term) => `<option value="${term.id}">${term.name}</option>`).join('');
  const list = state.supervisor.sessions.map((session) => `
    <tr>
      <td>${session.id}</td>
      <td>${session.course_id}</td>
      <td>${session.date}</td>
      <td>${session.start_time} - ${session.end_time}</td>
      <td>${session.is_locked ? 'Kilitli' : 'Açık'}</td>
    </tr>
  `).join('');
  return `
    <h2>${t('nav.sessions')}</h2>
    <form id="create-session" class="grid two">
      <label><span>Ders</span><select name="course_id" required><option value="">Seçiniz</option>${courseOptions}</select></label>
      <label><span>Dönem</span><select name="term_id" required><option value="">Seçiniz</option>${termOptions}</select></label>
      <label><span>${t('common.date')}</span><input name="date" type="date" required /></label>
      <label><span>${t('common.start')}</span><input name="start_time" type="time" required /></label>
      <label><span>${t('common.end')}</span><input name="end_time" type="time" required /></label>
      <div><button class="primary" type="submit">${t('common.create')}</button></div>
    </form>
    <table class="table" style="margin-top:1.5rem;">
      <thead><tr><th>ID</th><th>Ders</th><th>Tarih</th><th>Saat</th><th>Durum</th></tr></thead>
      <tbody>${list || '<tr><td colspan="5">Henüz oturum yok.</td></tr>'}</tbody>
    </table>
  `;
}

function attachSessionAdminEvents(content) {
  const form = content.querySelector('#create-session');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.course_id = Number(payload.course_id);
    payload.term_id = Number(payload.term_id);
    try {
      await apiRequest('/supervisor/schedule-sessions', { method: 'POST', body: payload });
      await loadSupervisorSessions();
      setFlash('Oturum oluşturuldu', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderReports() {
  return `
    <h2>${t('supervisor.reports.title')}</h2>
    <form id="report-form" class="grid two">
      <label><span>Sınıf ID</span><input name="classId" /></label>
      <label><span>Ders ID</span><input name="courseId" /></label>
      <label><span>Başlangıç</span><input name="from" type="date" /></label>
      <label><span>Bitiş</span><input name="to" type="date" /></label>
      <label><span>Format</span>
        <select name="format">
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
        </select>
      </label>
      <div><button class="primary" type="submit">Raporu Al</button></div>
    </form>
    <div id="report-result" style="margin-top:1.5rem;"></div>
  `;
}

function attachReportEvents(content) {
  const form = content.querySelector('#report-form');
  const resultEl = content.querySelector('#report-result');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const params = new URLSearchParams();
    const data = Object.fromEntries(new FormData(form).entries());
    Object.entries(data).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });
    try {
      if (data.format === 'csv') {
        window.open(`${API_BASE}/supervisor/reports/attendance?${params.toString()}`);
      } else {
        const json = await apiRequest(`/supervisor/reports/attendance?${params.toString()}`);
        resultEl.innerHTML = `<pre>${JSON.stringify(json, null, 2)}</pre>`;
      }
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderFlags() {
  const flags = state.supervisor.featureFlags;
  const absenceOnlyUnexcused = flags?.absence_only_unexcused?.enabled ? 'checked' : '';
  const graceMinutes = flags?.attendance_grace_period?.minutes ?? 0;
  return `
    <h2>${t('supervisor.featureFlags')}</h2>
    <form id="flags-form" class="grid">
      <label class="card" style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <strong>Sadece izinsiz devamsızlık hesaplansın</strong>
          <p>Bu özellik açılırsa sadece "İzinsiz" kayıtlar yüzdelere dahil edilir.</p>
        </div>
        <input type="checkbox" name="absence_only_unexcused" ${absenceOnlyUnexcused} />
      </label>
      <label class="card" style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <strong>Ders sonrası ek süre (dakika)</strong>
          <p>Öğretmenin yoklamayı güncelleyebileceği ek süre.</p>
        </div>
        <input type="number" name="attendance_grace_period" value="${graceMinutes}" min="0" />
      </label>
      <div><button class="primary" type="submit">Kaydet</button></div>
    </form>
  `;
}

function attachFlagEvents(content) {
  const form = content.querySelector('#flags-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const absence = form.elements['absence_only_unexcused'].checked;
    const grace = Number(form.elements['attendance_grace_period'].value || 0);
    try {
      await apiRequest('/feature-flags/absence_only_unexcused', { method: 'PUT', body: { enabled: absence } });
      await apiRequest('/feature-flags/attendance_grace_period', { method: 'PUT', body: { minutes: grace } });
      await loadFeatureFlags();
      setFlash('Özellikler güncellendi', 'success');
      renderSupervisorContent();
    } catch (error) {
      setFlash(error.message, 'alert');
    }
  });
}

function renderNotifications() {
  if (!state.notifications.length) {
    return `<p>${t('notifications.empty')}</p>`;
  }
  return `
    <h2>${t('nav.notifications')}</h2>
    <div class="grid">
      ${state.notifications.map((notification) => `
        <div class="card" style="background:rgba(37,99,235,0.07);">
          <strong>${notification.title}</strong>
          <p>${notification.body}</p>
          <small>${new Date(notification.created_at).toLocaleString('tr-TR')}</small>
          ${notification.read_at ? '<span class="badge">Okundu</span>' : `<button data-read="${notification.id}" class="primary" style="margin-top:0.75rem;">${t('notifications.markRead')}</button>`}
        </div>
      `).join('')}
    </div>
  `;
}

function attachNotificationEvents(content) {
  content.querySelectorAll('button[data-read]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.read;
      try {
        await apiRequest(`/notifications/${id}/read`, { method: 'POST' });
        state.notifications = await apiRequest('/notifications');
        renderSupervisorContent();
      } catch (error) {
        setFlash(error.message, 'alert');
      }
    });
  });
}

function renderTeacher() {
  const container = document.createElement('div');
  container.className = 'grid two';
  container.innerHTML = `
    ${renderFlash()}
    <div class="card" style="grid-column: span 2;">
      <h2>${t('teacher.classes')}</h2>
      <div class="grid two">
        ${state.teacher.classes.map((cls) => `
          <button class="card" data-class="${cls.id}" style="border:none;text-align:left;cursor:pointer;">
            <div class="badge"><span class="dot" style="background:${cls.display_color}"></span>${cls.name}</div>
            <p>${cls.grade}. sınıf ${cls.branch}</p>
          </button>
        `).join('') || '<p>Sınıf bulunamadı.</p>'}
      </div>
    </div>
    <div class="card" id="teacher-sessions" style="grid-column: span 1;"></div>
    <div class="card" id="teacher-attendance" style="grid-column: span 1;"></div>
  `;
  appEl.appendChild(container);
  container.querySelectorAll('button[data-class]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const classId = Number(btn.dataset.class);
      state.teacher.selectedClass = classId;
      await loadTeacherSessions(classId);
      renderTeacherPanels();
    });
  });
  renderTeacherPanels();
}

function renderTeacherPanels() {
  const sessionsEl = document.getElementById('teacher-sessions');
  const attendanceEl = document.getElementById('teacher-attendance');
  if (!sessionsEl || !attendanceEl) return;
  sessionsEl.innerHTML = `
    <h3>${t('teacher.sessions')}</h3>
    <div class="grid">
      ${state.teacher.sessions.map((session) => `
        <button class="card" data-session="${session.id}" style="border:none;text-align:left;cursor:pointer;">
          <strong>${session.course_name}</strong>
          <p>${session.date} ${session.start_time}-${session.end_time}</p>
          <small>${session.is_locked ? 'Kilitle' : 'Açık'}</small>
        </button>
      `).join('') || `<p>${t('teacher.noSessions')}</p>`}
    </div>
  `;
  sessionsEl.querySelectorAll('button[data-session]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const sessionId = Number(btn.dataset.session);
      await loadTeacherAttendance(sessionId);
      renderTeacherAttendance();
    });
  });
  renderTeacherAttendance();
}

function renderTeacherAttendance() {
  const attendanceEl = document.getElementById('teacher-attendance');
  if (!attendanceEl) return;
  if (!state.teacher.selectedSession) {
    attendanceEl.innerHTML = `<p>${t('teacher.attendance')} için oturum seçiniz.</p>`;
    return;
  }
  const session = state.teacher.selectedSession;
  const rows = state.teacher.attendance.map((item, index) => `
    <tr>
      <td>${item.student_name}</td>
      <td class="attendance-status">
        ${['present','excused','unexcused'].map((status) => `
          <label><input type="radio" name="student-${index}" value="${status}" ${item.status === status ? 'checked' : ''} data-student="${item.student_id}" /> ${t(`common.status.${status}`)}</label>
        `).join('')}
      </td>
    </tr>
  `).join('');
  attendanceEl.innerHTML = `
    <h3>${t('teacher.attendance')}</h3>
    <p><strong>${session.course_name || session.course_id}</strong> | ${session.date} ${session.start_time}-${session.end_time}</p>
    <form id="attendance-form">
      <table class="table">
        <thead><tr><th>Öğrenci</th><th>Durum</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <button class="primary" type="submit">${t('teacher.save')}</button>
    </form>
  `;
  const form = attendanceEl.querySelector('#attendance-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const inputs = Array.from(form.querySelectorAll('input[type="radio"]:checked'));
    const items = inputs.map((input) => ({
      student_id: Number(input.dataset.student),
      status: input.value,
    }));
    try {
      await apiRequest(`/teacher/sessions/${session.id}/attendance`, { method: 'POST', body: { items } });
      setFlash(t('alerts.attendanceSaved'), 'success');
      await loadTeacherAttendance(session.id);
      renderTeacherAttendance();
    } catch (error) {
      setFlash(error.message || t('alerts.attendanceLocked'), 'alert');
    }
  });
}

function renderStudent() {
  const container = document.createElement('div');
  container.className = 'grid';
  container.innerHTML = `
    ${renderFlash()}
    <div class="card">
      <h2>${t('student.courses')}</h2>
      <div class="grid two">
        ${state.student.courses.map((course) => {
          const summary = state.student.summaries[course.id];
          const percent = summary?.percent?.toFixed(1) || '0.0';
          const threshold = summary?.threshold || 30;
          const exceeded = Number(percent) >= threshold;
          return `
            <div class="card" style="border-top:4px solid ${course.display_color};">
              <h3>${course.name}</h3>
              <p>${course.class_name}</p>
              <p>${t('student.attendanceRate')}: %${percent}</p>
              <p>${t('student.thresholdInfo')}: %${threshold}</p>
              ${exceeded ? `<div class="alert">Eşik aşıldı!</div>` : ''}
            </div>
          `;
        }).join('') || '<p>Ders bulunamadı.</p>'}
      </div>
    </div>
    <div class="card">
      <h2>${t('nav.notifications')}</h2>
      ${state.notifications.length ? state.notifications.map((n) => `
        <div class="card" style="background:rgba(37,99,235,0.06);">
          <strong>${n.title}</strong>
          <p>${n.body}</p>
          <small>${new Date(n.created_at).toLocaleString('tr-TR')}</small>
        </div>
      `).join('') : `<p>${t('notifications.empty')}</p>`}
    </div>
  `;
  appEl.appendChild(container);
}

function renderHeader() {
  if (!state.user) {
    userInfoEl.innerHTML = '';
    return;
  }
  const unread = state.notifications.filter((n) => !n.read_at).length;
  userInfoEl.innerHTML = `
    <div style="display:flex;align-items:center;gap:1rem;">
      <span>${state.user.name} (${state.user.role})</span>
      <span class="badge"><span class="dot" style="background:${unread ? '#ef4444' : '#22c55e'}"></span>${unread} bildirim</span>
      <button class="primary" id="logout-btn">${t('auth.logout')}</button>
    </div>
  `;
  document.getElementById('logout-btn').addEventListener('click', handleLogout);
}

async function markNotification(id) {
  try {
    await apiRequest(`/notifications/${id}/read`, { method: 'POST' });
    state.notifications = await apiRequest('/notifications');
    render();
  } catch (error) {
    console.error(error);
  }
}

async function init() {
  restoreSession();
  if (state.user) {
    await loadInitialData();
  }
  render();
}

function render() {
  appEl.innerHTML = '';
  renderHeader();
  if (!state.user) {
    renderLogin();
    return;
  }
  if (state.user.role === 'supervisor') {
    renderSupervisor();
  } else if (state.user.role === 'teacher') {
    renderTeacher();
  } else if (state.user.role === 'student') {
    renderStudent();
  }
}

init();
