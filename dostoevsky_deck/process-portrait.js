const sharp = require("sharp");

const W = 1300, H = 1746;

async function run() {
  const vignetteSvg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="v" cx="42%" cy="38%" r="70%">
        <stop offset="0%" stop-color="#000000" stop-opacity="0"/>
        <stop offset="60%" stop-color="#120A0D" stop-opacity="0.15"/>
        <stop offset="100%" stop-color="#120A0D" stop-opacity="0.75"/>
      </radialGradient>
      <linearGradient id="topfade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1C1013" stop-opacity="0.55"/>
        <stop offset="18%" stop-color="#1C1013" stop-opacity="0"/>
        <stop offset="82%" stop-color="#1C1013" stop-opacity="0"/>
        <stop offset="100%" stop-color="#1C1013" stop-opacity="0.65"/>
      </linearGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#v)"/>
    <rect width="${W}" height="${H}" fill="url(#topfade)"/>
  </svg>`;

  await sharp("dostoevsky-portrait-raw.jpg")
    .resize(W, H, { fit: "cover", position: "attention" })
    .modulate({ brightness: 0.92, saturation: 0.55 })
    .tint({ r: 200, g: 150, b: 160 })
    .linear(1.08, -18)
    .composite([{ input: Buffer.from(vignetteSvg) }])
    .png()
    .toFile("art-portrait.png");

  console.log("wrote art-portrait");
}
run();
