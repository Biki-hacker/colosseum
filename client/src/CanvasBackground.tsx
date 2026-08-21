import { useEffect, useRef } from "react";

export function CanvasBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animFrame: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", handleResize);

    const gridSize = 48;

    const render = () => {
      // 1. Rich Deep Terracotta Base
      ctx.fillStyle = "#3D1A14";
      ctx.fillRect(0, 0, width, height);

      // 2. Radial Warmth Vignette
      const bgGrad = ctx.createRadialGradient(
        width / 2,
        height * 0.35,
        100,
        width / 2,
        height / 2,
        Math.max(width, height) * 0.85
      );
      bgGrad.addColorStop(0, "rgba(107, 53, 42, 0.65)");
      bgGrad.addColorStop(0.7, "rgba(61, 26, 20, 0.9)");
      bgGrad.addColorStop(1, "rgba(40, 15, 11, 1)");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // 3. Crisp Warm Cream Grid Lines
      ctx.strokeStyle = "rgba(255, 241, 166, 0.08)";
      ctx.lineWidth = 1;

      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }

      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // 4. Subtle Intersection Dots
      ctx.fillStyle = "rgba(255, 241, 166, 0.18)";
      for (let x = 0; x < width; x += gridSize) {
        for (let y = 0; y < height; y += gridSize) {
          ctx.beginPath();
          ctx.arc(x, y, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      animFrame = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animFrame);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return <canvas ref={canvasRef} className="clay-canvas-bg" />;
}
