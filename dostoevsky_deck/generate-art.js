const sharp = require("sharp");
const fs = require("fs");

// Darker mood palette (kept legible: mid-tones bright enough to read at slide scale)
const BG0 = "#1C1013"; // near-black maroon
const BG1 = "#2E1620"; // deep maroon
const BERRY = "#9B3D57";
const BERRY2 = "#7A2E45";
const ROSE = "#C08B92";
const CREAM = "#E9D9CC";
const GLOW = "#F0C08A"; // candle glow
const INK = "#120A0D";

function wrap(inner, w, h, defs = "") {
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${BG1}"/>
        <stop offset="100%" stop-color="${BG0}"/>
      </linearGradient>
      <radialGradient id="vignette" cx="50%" cy="35%" r="95%">
        <stop offset="0%" stop-color="${BG1}" stop-opacity="0"/>
        <stop offset="70%" stop-color="${INK}" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="${INK}" stop-opacity="0.6"/>
      </radialGradient>
      ${defs}
    </defs>
    <rect width="${w}" height="${h}" fill="url(#bgGrad)"/>
    ${inner}
    <rect width="${w}" height="${h}" fill="url(#vignette)"/>
  </svg>`;
}

const W = 1200, H = 1600;

// ---------- 1. Raskolnikov — axe + staircase ----------
const raskolnikov = wrap(`
  <radialGradient id="glow1" cx="50%" cy="30%" r="48%">
    <stop offset="0%" stop-color="${BERRY}" stop-opacity="0.85"/>
    <stop offset="100%" stop-color="${BERRY}" stop-opacity="0"/>
  </radialGradient>
  <circle cx="${W*0.5}" cy="${H*0.32}" r="520" fill="url(#glow1)"/>
  <!-- staircase silhouette -->
  <g opacity="0.95">
    ${Array.from({length: 9}).map((_,i)=>{
      const y = 900 + i*70; const w = 1200 - i*40;
      return `<rect x="${(1200-w)/2}" y="${y}" width="${w}" height="16" fill="${i%2===0? '#3A2029':'#4A2632'}"/>`;
    }).join("")}
  </g>
  <!-- door glow at top of stairs -->
  <rect x="460" y="750" width="280" height="170" rx="8" fill="${GLOW}" opacity="0.35"/>
  <!-- axe silhouette -->
  <g transform="translate(600,560) rotate(28)">
    <rect x="-14" y="-20" width="28" height="360" rx="8" fill="#4A2A34"/>
    <path d="M -16 -195 L 18 -195 C 100 -190 165 -145 168 -80 C 170 -20 120 30 40 35 L -16 30 C -30 30 -30 -20 -16 -20 Z" fill="${BERRY}" stroke="${ROSE}" stroke-width="5" stroke-linejoin="round"/>
    <path d="M 150 -70 C 152 -25 118 15 45 22" fill="none" stroke="${CREAM}" stroke-width="3" opacity="0.55"/>
  </g>
`, W, H);

// ---------- 2. Notes from Underground — barred cellar window ----------
const podpolye = wrap(`
  <radialGradient id="glow2" cx="50%" cy="40%" r="42%">
    <stop offset="0%" stop-color="${GLOW}" stop-opacity="0.5"/>
    <stop offset="100%" stop-color="${GLOW}" stop-opacity="0"/>
  </radialGradient>
  <circle cx="${W*0.5}" cy="${H*0.42}" r="500" fill="url(#glow2)"/>
  <!-- brick wall texture -->
  <g opacity="0.9">
    ${Array.from({length: 16}).map((_,r)=>{
      const y = r*100; const offset = (r%2===0)?0:60;
      return Array.from({length: 11}).map((_,c)=>{
        const x = -60 + offset + c*120;
        return `<rect x="${x}" y="${y}" width="112" height="92" fill="none" stroke="#3A222B" stroke-width="4"/>`;
      }).join("");
    }).join("")}
  </g>
  <!-- window opening with glow -->
  <rect x="330" y="520" width="540" height="420" rx="10" fill="${GLOW}" opacity="0.4"/>
  <rect x="330" y="520" width="540" height="420" rx="10" fill="none" stroke="#241017" stroke-width="26"/>
  <!-- bars -->
  <g stroke="#180B10" stroke-width="20">
    <line x1="420" y1="520" x2="420" y2="940"/>
    <line x1="510" y1="520" x2="510" y2="940"/>
    <line x1="600" y1="520" x2="600" y2="940"/>
    <line x1="690" y1="520" x2="690" y2="940"/>
    <line x1="780" y1="520" x2="780" y2="940"/>
  </g>
  <g stroke="#180B10" stroke-width="18">
    <line x1="330" y1="650" x2="870" y2="650"/>
    <line x1="330" y1="800" x2="870" y2="800"/>
  </g>
`, W, H);

// ---------- 3. Grand Inquisitor — hooded figure + arch ----------
const inkvizitor = wrap(`
  <radialGradient id="glow3" cx="50%" cy="24%" r="34%">
    <stop offset="0%" stop-color="${GLOW}" stop-opacity="0.8"/>
    <stop offset="100%" stop-color="${GLOW}" stop-opacity="0"/>
  </radialGradient>
  <ellipse cx="${W*0.5}" cy="${H*0.22}" rx="300" ry="250" fill="url(#glow3)"/>
  <!-- gothic arch -->
  <path d="M 250 1350 L 250 650 C 250 380 950 380 950 650 L 950 1350 Z" fill="none" stroke="${BERRY2}" stroke-width="30"/>
  <path d="M 340 1350 L 340 680 C 340 470 860 470 860 680 L 860 1350 Z" fill="#241017"/>
  <!-- hooded figure silhouette -->
  <g transform="translate(600,1080)">
    <path d="M 0 -420 C 140 -420 210 -300 210 -150 C 210 -20 260 260 260 260 L -260 260 C -260 260 -210 -20 -210 -150 C -210 -300 -140 -420 0 -420 Z" fill="#0F080B" stroke="${BERRY}" stroke-width="3" opacity="0.98"/>
    <path d="M 0 -420 C 60 -420 95 -360 95 -300 C 95 -250 70 -220 0 -220 C -70 -220 -95 -250 -95 -300 C -95 -360 -60 -420 0 -420 Z" fill="#150B0F"/>
  </g>
  <!-- candle light dots -->
  <circle cx="600" cy="700" r="12" fill="${GLOW}"/>
  <circle cx="600" cy="700" r="46" fill="${GLOW}" opacity="0.3"/>
`, W, H);

// ---------- 4. Kirillov — candle & revolver on table ----------
const kirillov = wrap(`
  <radialGradient id="glow4" cx="42%" cy="42%" r="38%">
    <stop offset="0%" stop-color="${GLOW}" stop-opacity="0.85"/>
    <stop offset="100%" stop-color="${GLOW}" stop-opacity="0"/>
  </radialGradient>
  <circle cx="${W*0.42}" cy="${H*0.42}" r="440" fill="url(#glow4)"/>
  <!-- table -->
  <rect x="0" y="1080" width="${W}" height="60" fill="#3A2029"/>
  <rect x="0" y="1140" width="${W}" height="460" fill="#241017"/>
  <!-- candle -->
  <g transform="translate(480,760)">
    <rect x="-16" y="180" width="32" height="140" fill="#4A2A34"/>
    <path d="M -18 180 C -30 60 -30 -60 0 -140 C 30 -60 30 60 18 180 Z" fill="${GLOW}"/>
    <ellipse cx="0" cy="-150" rx="14" ry="30" fill="${GLOW}"/>
    <ellipse cx="0" cy="-155" rx="6" ry="16" fill="#FFF3DE"/>
  </g>
  <!-- revolver silhouette -->
  <g transform="translate(770,1000) rotate(-8)">
    <rect x="-180" y="6" width="300" height="26" rx="8" fill="#3A2029" stroke="${ROSE}" stroke-width="3"/>
    <circle cx="-70" cy="19" r="34" fill="#3A2029" stroke="${ROSE}" stroke-width="3"/>
    <path d="M -30 6 L 40 6 L 40 -60 C 40 -74 20 -74 16 -60 L 8 6 Z" fill="#3A2029" stroke="${ROSE}" stroke-width="3"/>
    <path d="M -110 32 C -120 70 -100 100 -70 110 C -60 90 -60 60 -70 32 Z" fill="#3A2029" stroke="${ROSE}" stroke-width="3"/>
  </g>
`, W, H);

// ---------- 5. Book stack (thematic, not literal covers) ----------
const books = wrap(`
  <radialGradient id="glowB" cx="50%" cy="30%" r="42%">
    <stop offset="0%" stop-color="${GLOW}" stop-opacity="0.5"/>
    <stop offset="100%" stop-color="${GLOW}" stop-opacity="0"/>
  </radialGradient>
  <circle cx="${W*0.5}" cy="${H*0.32}" r="480" fill="url(#glowB)"/>
  <g transform="translate(230,880)">
    <g transform="rotate(-3)">
      <rect x="0" y="0" width="740" height="86" rx="6" fill="#3A2029" stroke="${ROSE}" stroke-width="2"/>
      <rect x="18" y="14" width="704" height="58" rx="2" fill="none" stroke="${ROSE}" stroke-width="1.5" opacity="0.5"/>
    </g>
    <g transform="translate(30,84) rotate(2)">
      <rect x="0" y="0" width="700" height="86" rx="6" fill="#4A2632" stroke="${ROSE}" stroke-width="2"/>
      <rect x="18" y="14" width="664" height="58" rx="2" fill="none" stroke="${GLOW}" stroke-width="1.5" opacity="0.55"/>
    </g>
    <g transform="translate(-10,168) rotate(-4)">
      <rect x="0" y="0" width="760" height="90" rx="6" fill="${BERRY2}" stroke="${ROSE}" stroke-width="2"/>
      <rect x="18" y="16" width="724" height="58" rx="2" fill="none" stroke="${ROSE}" stroke-width="1.5" opacity="0.5"/>
    </g>
    <g transform="translate(140,258) rotate(1)">
      <rect x="0" y="0" width="500" height="94" rx="6" fill="#2A1218" stroke="${GLOW}" stroke-width="2.5"/>
      <rect x="20" y="16" width="460" height="62" rx="2" fill="none" stroke="${GLOW}" stroke-width="1.5" opacity="0.6"/>
    </g>
  </g>
  <!-- quill -->
  <g transform="translate(880,520) rotate(35)">
    <path d="M 0 0 C 60 -10 110 -70 100 -150 C 96 -180 70 -195 40 -180 C 10 -165 -10 -110 0 -40 Z" fill="${BERRY}" stroke="${ROSE}" stroke-width="4"/>
    <line x1="6" y1="-10" x2="-40" y2="130" stroke="#2A1218" stroke-width="10" stroke-linecap="round"/>
  </g>
`, W, H);

const items = [
  ["art-title", wrap(`
    <radialGradient id="glowT" cx="60%" cy="30%" r="48%">
      <stop offset="0%" stop-color="${BERRY}" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="${BERRY}" stop-opacity="0"/>
    </radialGradient>
    <circle cx="${W*0.6}" cy="${H*0.32}" r="580" fill="url(#glowT)"/>
    <g opacity="0.95">
      ${Array.from({length: 6}).map((_,i)=>`<rect x="${120+i*8}" y="${700+i*10}" width="${960-i*16}" height="10" fill="#3A2029"/>`).join("")}
    </g>
    <g transform="translate(600,760) rotate(20)">
      <rect x="-12" y="-30" width="24" height="440" rx="8" fill="#4A2A34"/>
      <path d="M -14 -215 L 16 -215 C 100 -210 168 -160 170 -85 C 172 -15 118 40 32 46 L -14 40 C -28 40 -28 -30 -14 -30 Z" fill="${BERRY}" stroke="${ROSE}" stroke-width="5" stroke-linejoin="round"/>
      <path d="M 152 -78 C 154 -25 116 20 36 32" fill="none" stroke="${CREAM}" stroke-width="3" opacity="0.55"/>
    </g>
  `, W, H)],
  ["art-raskolnikov", raskolnikov],
  ["art-podpolye", podpolye],
  ["art-inkvizitor", inkvizitor],
  ["art-kirillov", kirillov],
  ["art-books", books],
];

(async () => {
  for (const [name, svg] of items) {
    await sharp(Buffer.from(svg)).png().toFile(`${name}.png`);
    console.log("wrote", name);
  }
})();
