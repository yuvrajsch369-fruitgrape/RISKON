import { Nav } from '../sections/Nav.jsx';
import { Footer } from '../sections/Footer.jsx';
import { VisionHero } from '../vision/VisionHero.jsx';
import { TheBet } from '../vision/TheBet.jsx';
import { SixThings } from '../vision/SixThings.jsx';
import { HumanApproval } from '../vision/HumanApproval.jsx';
import { BusinessModel } from '../vision/BusinessModel.jsx';
import { CorityScenario } from '../vision/CorityScenario.jsx';
import { PeopleImpact } from '../vision/PeopleImpact.jsx';
import { Roadmap } from '../vision/Roadmap.jsx';
import { FutureWorkflow } from '../vision/FutureWorkflow.jsx';
import { WhereThisStands } from '../vision/WhereThisStands.jsx';

export default function FutureVisionPage() {
  return (
    <div className="font-sans text-ink">
      <Nav page="vision" />
      <main>
        <VisionHero />
        <TheBet />
        <SixThings />
        <HumanApproval />
        <BusinessModel />
        <CorityScenario />
        <PeopleImpact />
        <Roadmap />
        <FutureWorkflow />
        <WhereThisStands />
      </main>
      <Footer />
    </div>
  );
}
