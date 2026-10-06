interface TeamMember {
  name: string
  phone?: { display: string; tel: string }
  email: string
}

const TEAM: TeamMember[] = [
  { name: 'Ariel Cobden', phone: { display: '(203) 789-1608', tel: '+12037891608' }, email: 'ariel@campuscustoms.com' },
  { name: 'Luz Correa', email: 'luz@campuscustoms.com' },
]

export default function About() {
  return (
    <section>
      <h1>About Us</h1>
      <p className="lead about-lead">
        Campus Customs sells officially licensed Yale merchandise from our store at 57 Broadway in New Haven.
      </p>

      <div className="about-grid">
        <section className="card" aria-labelledby="location-heading">
          <h2 id="location-heading">New Haven store</h2>
          <address className="about-address">
            57 Broadway
            <br />
            New Haven, CT 06511
            <br />
            US
          </address>
          <dl className="contact-list">
            <dt>Phone</dt>
            <dd>
              <a href="tel:+14753014205">(475) 301-4205</a>
            </dd>
            <dt>Fax</dt>
            <dd>(203) 865-6408</dd>
            <dt>Email</dt>
            <dd>
              <a href="mailto:team@campuscustoms.com">team@campuscustoms.com</a>
            </dd>
            <dt>Web</dt>
            <dd>
              <a href="https://www.campuscustoms.com" target="_blank" rel="noopener noreferrer">
                www.CampusCustoms.com
              </a>
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="team-heading">
          <h2 id="team-heading">Our team</h2>
          <ul className="team-list">
            {TEAM.map((member) => (
              <li key={member.name} className="team-member">
                <h3>{member.name}</h3>
                <dl className="contact-list">
                  {member.phone && (
                    <>
                      <dt>Phone</dt>
                      <dd>
                        <a href={`tel:${member.phone.tel}`}>{member.phone.display}</a>
                      </dd>
                    </>
                  )}
                  <dt>Email</dt>
                  <dd>
                    <a href={`mailto:${member.email}`}>{member.email}</a>
                  </dd>
                </dl>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  )
}
