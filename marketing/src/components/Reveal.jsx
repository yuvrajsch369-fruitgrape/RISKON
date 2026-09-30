import { motion } from 'motion/react';

// Shared scroll-reveal: fade + slight upward slide, once per element, tuned
// to be noticeable without feeling like a slideshow. Used everywhere instead
// of repeating the same whileInView/viewport boilerplate in every section.
const EASE = [0.22, 1, 0.36, 1];

export function Reveal({ children, delay = 0, y = 18, className = '', as = 'div', ...rest }) {
  const Comp = motion[as] ?? motion.div;
  return (
    <Comp
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6, delay, ease: EASE }}
      className={className}
      {...rest}
    >
      {children}
    </Comp>
  );
}

const containerVariants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.09, delayChildren: 0.03 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};

export function Stagger({ children, className = '' }) {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: '-80px' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className = '' }) {
  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  );
}
