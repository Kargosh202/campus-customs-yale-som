import { Link } from 'react-router-dom'
import HandsomeDanIntro from '../components/HandsomeDanIntro'

export default function Home() {
  return (
    <>
      <HandsomeDanIntro />
      <section className="hero hero-dan">
        {/* Decorative background: the first Handsome Dan, Yale's bulldog mascot, in 1889. */}
        <img className="hero-dan-photo" src="/images/handsome-dan-1889.jpg" alt="" />
        <div className="hero-content">
          <p className="badge">Officially Licensed Yale Merchandise</p>
          <h1>Campus Customs</h1>
          <p className="lead">Yale apparel for students, alumni, and families. Boola boola!</p>
          <Link to="/products" className="button large">
            Shop Products
          </Link>
        </div>
        <p className="hero-credit">
          Handsome Dan I, Yale's first bulldog mascot, 1889. Photo: Yale Manuscripts &amp; Archives
        </p>
      </section>

      <section className="card visit">
        <h2>Visit the store</h2>
        <address>
          57 Broadway
          <br />
          New Haven, CT 06511
        </address>
      </section>
    </>
  )
}
