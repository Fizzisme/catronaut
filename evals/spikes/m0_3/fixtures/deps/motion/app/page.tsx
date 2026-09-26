"use client";

import { motion, useScroll, useTransform } from "motion/react";

export default function Home() {
  const { scrollYProgress } = useScroll();
  const scale = useTransform(scrollYProgress, [0, 1], [1, 1.4]);
  return (
    <section className="space-y-6">
      <motion.h1
        data-testid="heading"
        className="font-display text-6xl"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        Motion works
      </motion.h1>
      <motion.div style={{ scale }} className="h-40 w-40 rounded-3xl bg-brand" data-testid="probe" />
      <div className="h-[150vh]" />
    </section>
  );
}
