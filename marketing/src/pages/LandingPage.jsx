import { Nav } from '../sections/Nav.jsx';
import { Hero } from '../sections/Hero.jsx';
import { Problem } from '../sections/Problem.jsx';
import { Loop } from '../sections/Loop.jsx';
import { Differentiators } from '../sections/Differentiators.jsx';
import { WorkflowByRole } from '../sections/WorkflowByRole.jsx';
import { Adoption } from '../sections/Adoption.jsx';
import { Comparison } from '../sections/Comparison.jsx';
import { RealityCheck } from '../sections/RealityCheck.jsx';
import { FinalCTA } from '../sections/FinalCTA.jsx';
import { Footer } from '../sections/Footer.jsx';

export default function LandingPage() {
  return (
    <div className="font-sans text-ink">
      <Nav page="landing" />
      <main>
        <Hero />
        <Problem />
        <Loop />
        <Differentiators />
        <WorkflowByRole />
        <Adoption />
        <Comparison />
        <RealityCheck />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
