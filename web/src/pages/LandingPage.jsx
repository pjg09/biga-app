import { useEffect } from 'react';
import Navbar from '../components/Navbar';
import Hero from '../components/Hero';
import Mission from '../components/Mission';
import Features from '../components/Features';
import Audience from '../components/Audience';
import Vision from '../components/Vision';
import CallToAction from '../components/CallToAction';
import Footer from '../components/Footer';

export default function LandingPage() {
  useEffect(() => { document.title = 'BIGA - Tecnología Educativa'; }, []);

  return (
    <>
      <Navbar />
      <main id="main-content">
        <Hero />
        <Mission />
        <Features />
        <Audience />
        <Vision />
        <CallToAction />
      </main>
      <Footer />
    </>
  );
}
