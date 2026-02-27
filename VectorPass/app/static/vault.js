/* global window, navigator, fetch, document */
'use strict'

// ── Password generator ────────────────────────────────────────────────────────
const _CHARS = {
  lower:   'abcdefghijklmnopqrstuvwxyz',
  upper:   'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  digits:  '0123456789',
  symbols: '!@#$%^&*()-_=+[]{}|;:,.<>?'
}

function _randomInt (max) {
  const arr = new Uint32Array(1)
  window.crypto.getRandomValues(arr)
  return arr[0] % max
}

function generatePassword (length, useLower, useUpper, useDigits, useSymbols) {
  length = Math.max(8, Math.min(128, length || 20))
  let pool = ''
  const required = []
  if (useLower)   { pool += _CHARS.lower;   required.push(_CHARS.lower[_randomInt(_CHARS.lower.length)]) }
  if (useUpper)   { pool += _CHARS.upper;   required.push(_CHARS.upper[_randomInt(_CHARS.upper.length)]) }
  if (useDigits)  { pool += _CHARS.digits;  required.push(_CHARS.digits[_randomInt(_CHARS.digits.length)]) }
  if (useSymbols) { pool += _CHARS.symbols; required.push(_CHARS.symbols[_randomInt(_CHARS.symbols.length)]) }
  if (!pool) pool = _CHARS.lower + _CHARS.upper + _CHARS.digits

  const arr = []
  for (let i = 0; i < length; i++) arr.push(pool[_randomInt(pool.length)])
  // Inject required chars at random positions
  required.forEach(c => { arr[_randomInt(arr.length)] = c })
  // Fisher-Yates shuffle
  for (let i = arr.length - 1; i > 0; i--) {
    const j = _randomInt(i + 1);
    [arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr.join('')
}

// ── Strength meter ────────────────────────────────────────────────────────────
function passwordStrength (pw) {
  if (!pw) return { score: 0, label: '', color: '' }
  let score = 0
  if (pw.length >= 8)  score++
  if (pw.length >= 12) score++
  if (pw.length >= 16) score++
  if (/[a-z]/.test(pw)) score++
  if (/[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  // Entropy bonus for length
  if (pw.length >= 20) score++

  if (score <= 2) return { score, label: 'Very Weak', color: '#dc3545', pct: 15 }
  if (score <= 3) return { score, label: 'Weak',      color: '#fd7e14', pct: 30 }
  if (score <= 4) return { score, label: 'Fair',      color: '#ffc107', pct: 55 }
  if (score <= 5) return { score, label: 'Good',      color: '#20c997', pct: 75 }
  return                 { score, label: 'Strong',    color: '#198754', pct: 100 }
}

// ── Public API ────────────────────────────────────────────────────────────────
window.VectorPass = {
  togglePassword: function (inputId, btn) {
    const el = document.getElementById(inputId)
    if (!el) return
    if (el.type === 'password') { el.type = 'text';     btn.textContent = 'Hide' }
    else                        { el.type = 'password'; btn.textContent = 'Show' }
  },

  revealAndCopy: async function (btn) {
    const entryId = btn.getAttribute('data-entry-id')
    if (!entryId) return
    btn.disabled = true
    const original = btn.textContent
    btn.textContent = 'Working…'
    try {
      const res = await fetch(`/api/entries/${encodeURIComponent(entryId)}/reveal`, { credentials: 'same-origin' })
      if (res.status === 401) { window.location.href = '/login';  return }
      if (res.status === 403) { window.location.href = '/unlock'; return }
      if (!res.ok) throw new Error(`Failed: ${res.status}`)
      const data = await res.json()
      await navigator.clipboard.writeText(data.password || '')
      btn.textContent = 'Copied!'
      setTimeout(() => { btn.textContent = original }, 1200)
    } catch (e) {
      btn.textContent = 'Error'
      setTimeout(() => { btn.textContent = original }, 1200)
    } finally {
      btn.disabled = false
    }
  },

  generatePassword,
  passwordStrength
}

// ── Vault edit page: generator + strength meter ───────────────────────────────
;(function () {
  const pwInput = document.getElementById('vpPassword')
  if (!pwInput) return

  // --- Strength bar ---
  const strengthBar  = document.getElementById('vpStrengthBar')
  const strengthText = document.getElementById('vpStrengthText')

  function updateStrength () {
    if (!strengthBar || !strengthText) return
    const s = passwordStrength(pwInput.value)
    strengthBar.style.width = (s.pct || 0) + '%'
    strengthBar.style.background = s.color || '#6c757d'
    strengthText.textContent = s.label || ''
    strengthText.style.color = s.color || '#6c757d'
  }
  pwInput.addEventListener('input', updateStrength)
  updateStrength()

  // --- Generator modal trigger ---
  const genBtn = document.getElementById('vpGenBtn')
  if (!genBtn) return

  const genLength  = document.getElementById('vpGenLength')
  const genLower   = document.getElementById('vpGenLower')
  const genUpper   = document.getElementById('vpGenUpper')
  const genDigits  = document.getElementById('vpGenDigits')
  const genSymbols = document.getElementById('vpGenSymbols')
  const genPreview = document.getElementById('vpGenPreview')
  const genUse     = document.getElementById('vpGenUse')
  const genRefresh = document.getElementById('vpGenRefresh')

  function refreshPreview () {
    if (!genPreview) return
    const pw = generatePassword(
      parseInt(genLength ? genLength.value : 20),
      genLower   ? genLower.checked   : true,
      genUpper   ? genUpper.checked   : true,
      genDigits  ? genDigits.checked  : true,
      genSymbols ? genSymbols.checked : false
    )
    genPreview.value = pw
  }

  if (genRefresh) genRefresh.addEventListener('click', refreshPreview)
  if (genLength)  genLength.addEventListener('input', refreshPreview)
  if (genLower)   genLower.addEventListener('change', refreshPreview)
  if (genUpper)   genUpper.addEventListener('change', refreshPreview)
  if (genDigits)  genDigits.addEventListener('change', refreshPreview)
  if (genSymbols) genSymbols.addEventListener('change', refreshPreview)

  // Refresh preview every time the modal opens
  const genModalEl = document.getElementById('vpGenModal')
  if (genModalEl) genModalEl.addEventListener('show.bs.modal', refreshPreview)

  if (genUse) {
    genUse.addEventListener('click', function () {
      if (!genPreview) return
      pwInput.value = genPreview.value
      pwInput.type = 'text'
      const showBtn = document.getElementById('vpShowBtn')
      if (showBtn) showBtn.textContent = 'Hide'
      updateStrength()
      // Close Bootstrap modal
      const modalEl = document.getElementById('vpGenModal')
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl)
        if (modal) modal.hide()
      }
    })
  }

  refreshPreview()
})()

// ── Vault list: search + tag filter ──────────────────────────────────────────
;(function () {
  const search = document.getElementById('vpSearch')
  const table  = document.getElementById('vpTable')
  if (!search || !table) return

  const rows = Array.from(table.querySelectorAll('tbody tr'))
  let activeTag = ''

  function applyFilters () {
    const q = (search.value || '').toLowerCase().trim()
    for (const r of rows) {
      const txt = (r.textContent || '').toLowerCase()
      const matchSearch = !q || txt.includes(q)
      const matchTag    = !activeTag || txt.includes(activeTag.toLowerCase())
      r.style.display = matchSearch && matchTag ? '' : 'none'
    }
  }

  search.addEventListener('input', applyFilters)

  // Tag badge click-to-filter
  document.querySelectorAll('.vp-tag-filter').forEach(function (badge) {
    badge.style.cursor = 'pointer'
    badge.addEventListener('click', function () {
      const tag = badge.dataset.tag || ''
      if (activeTag === tag) {
        activeTag = ''
        document.querySelectorAll('.vp-tag-filter').forEach(b => b.classList.remove('active', 'text-bg-primary'))
        document.querySelectorAll('.vp-tag-filter').forEach(b => b.classList.add('text-bg-secondary'))
      } else {
        activeTag = tag
        document.querySelectorAll('.vp-tag-filter').forEach(b => {
          b.classList.remove('active', 'text-bg-primary')
          b.classList.add('text-bg-secondary')
        })
        badge.classList.add('active', 'text-bg-primary')
        badge.classList.remove('text-bg-secondary')
      }
      applyFilters()
    })
  })
})()
