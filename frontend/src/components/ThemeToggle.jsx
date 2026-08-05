import { useEffect, useState } from 'react'

function getInitialTheme() {
  return localStorage.getItem('literature-ai:theme') || 'system'
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') {
      root.removeAttribute('data-theme')
    } else {
      root.setAttribute('data-theme', theme)
    }
    localStorage.setItem('literature-ai:theme', theme)
  }, [theme])

  const cycle = () => {
    setTheme((t) => (t === 'system' ? 'light' : t === 'light' ? 'dark' : 'system'))
  }

  const label = theme === 'system' ? 'System' : theme === 'light' ? 'Light' : 'Dark'

  return (
    <button type="button" className="theme-toggle" onClick={cycle} title="Toggle theme">
      {label}
    </button>
  )
}
