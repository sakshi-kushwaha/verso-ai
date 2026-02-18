export function getWsBaseUrl() {
  if (window.location.hostname === 'localhost') {
    return 'ws://localhost:8000'
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}`
}

export function getAuthToken() {
  return localStorage.getItem('verso_token')
}
