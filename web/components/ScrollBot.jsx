"use client";

import { useEffect, useRef } from "react";

/**
 * Scroll-reactive character.
 * - gentle idle autoplay so it's alive on load
 * - scroll velocity scrubs the frame sequence and tilts the character
 * - mouse parallax for depth
 * - reduced motion → single static frame
 */
export default function ScrollBot({
  name = "robot",
  frames = 63,
  size = 460,
  className = "",
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;

    const imgs = [];
    let loaded = 0;
    for (let i = 0; i < frames; i++) {
      const img = new Image();
      img.src = `/characters/${name}/f_${String(i).padStart(3, "0")}.png`;
      img.onload = () => (loaded += 1);
      imgs.push(img);
    }

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let frame = 0;          // fractional frame cursor
    let vel = 0;            // scroll velocity (smoothed)
    let lastY = window.scrollY;
    let px = 0, py = 0;     // pointer parallax target
    let sx = 0, sy = 0;     // smoothed parallax
    let raf;

    const onScroll = () => {
      const y = window.scrollY;
      vel += (y - lastY) * 0.12;   // scroll injects energy
      lastY = y;
    };
    const onPointer = (e) => {
      px = (e.clientX / window.innerWidth - 0.5) * 18;
      py = (e.clientY / window.innerHeight - 0.5) * 12;
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pointermove", onPointer, { passive: true });

    const draw = () => {
      raf = requestAnimationFrame(draw);
      if (!loaded) return;

      // decay scroll energy, keep a gentle idle drift
      vel *= 0.9;
      const advance = reduced ? 0 : 0.22 + vel;
      frame = (frame + advance + frames * 1000) % frames;

      sx += (px - sx) * 0.06;
      sy += (py - sy) * 0.06;

      const idx = Math.floor(frame);
      const img = imgs[idx];
      if (!img || !img.complete || !img.naturalWidth) return;

      const tilt = reduced ? 0 : Math.max(-0.12, Math.min(0.12, vel * 0.01));
      const scale = 1 + Math.min(0.06, Math.abs(vel) * 0.004);

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);
      ctx.translate(size / 2 + sx, size / 2 + sy);
      ctx.rotate(tilt);
      ctx.scale(scale, scale);
      ctx.drawImage(img, -size / 2, -size / 2, size, size);
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pointermove", onPointer);
    };
  }, [name, frames, size]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: size, height: size, maxWidth: "88vw", maxHeight: "88vw" }}
      aria-label="Genlineage robot"
      role="img"
    />
  );
}
