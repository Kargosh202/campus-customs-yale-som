import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth, type RegisterInput } from '../auth'

const MIN_PASSWORD = 8

const EMPTY: RegisterInput = { first_name: '', last_name: '', email: '', password: '', confirm_password: '' }

export default function CreateAccount() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<RegisterInput>(EMPTY)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/" replace />

  const update = (field: keyof RegisterInput) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const mismatch = form.confirm_password !== '' && form.password !== form.confirm_password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (form.password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`)
      return
    }
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await register(form)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account.')
      setSubmitting(false)
    }
  }

  return (
    <section className="card form-card">
      <h1>Create Account</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>
            First name
            <input
              type="text"
              name="first_name"
              autoComplete="given-name"
              required
              value={form.first_name}
              onChange={update('first_name')}
            />
          </label>
          <label>
            Last name
            <input
              type="text"
              name="last_name"
              autoComplete="family-name"
              required
              value={form.last_name}
              onChange={update('last_name')}
            />
          </label>
        </div>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" required value={form.email} onChange={update('email')} />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            value={form.password}
            onChange={update('password')}
            aria-describedby="password-hint"
          />
          <span id="password-hint" className="field-hint">
            At least {MIN_PASSWORD} characters
          </span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            name="confirm_password"
            autoComplete="new-password"
            required
            value={form.confirm_password}
            onChange={update('confirm_password')}
            aria-invalid={mismatch}
          />
          {mismatch && <span className="field-hint error">Passwords do not match</span>}
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
