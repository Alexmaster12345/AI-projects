/* global window, navigator, fetch */

window.VectorPass = {
  togglePassword: function (inputId, btn) {
    const el = document.getElementById(inputId)
    if (!el) return
    if (el.type === 'password') {
      el.type = 'text'
      btn.textContent = 'Hide'
    } else {
      el.type = 'password'
      btn.textContent = 'Show'
    }
  },

  revealAndCopy: async function (btn) {
    const entryId = btn.getAttribute('data-entry-id')
    if (!entryId) return

    btn.disabled = true
    const original = btn.textContent
    btn.textContent = 'Working…'

    try {
      const res = await fetch(`/api/entries/${encodeURIComponent(entryId)}/reveal`, { credentials: 'same-origin' })
      if (res.status === 401) {
        window.location.href = '/login'
        return
      }
      if (res.status === 403) {
        window.location.href = '/unlock'
        return
      }
      if (!res.ok) {
        throw new Error(`Failed: ${res.status}`)
      }
      const data = await res.json()
      const pw = data.password || ''
      await navigator.clipboard.writeText(pw)
      btn.textContent = 'Copied!'
      setTimeout(() => { btn.textContent = original }, 1000)
    } catch (e) {
      console.error(e)
      btn.textContent = 'Error'
      setTimeout(() => { btn.textContent = original }, 1000)
    } finally {
      btn.disabled = false
    }
  }
}

;(function () {
  // Simple client-side search on the vault list table
  const search = document.getElementById('vpSearch')
  const table = document.getElementById('vpTable')
  if (!search || !table) return

  const rows = Array.from(table.querySelectorAll('tbody tr'))
  search.addEventListener('input', function () {
    const q = (search.value || '').toLowerCase().trim()
    for (const r of rows) {
      const txt = (r.textContent || '').toLowerCase()
      r.style.display = txt.includes(q) ? '' : 'none'
    }
  })
})()
