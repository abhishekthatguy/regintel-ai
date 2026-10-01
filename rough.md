
**Original prompt inside code in javascript build :** 


return $input.all().map(item => {
  const bp = item.json.blueprint;

  const prompt = [
    `TEMPLATE: ${bp.templateLabel}`,
    "",
    "IDENTITY LOCK:",
    "- Preserve the subject’s identity exactly.",
    "- Do not alter facial features or proportions.",
    "",
    "STYLE BLUEPRINT:",
    bp.styleBlueprint
  ].join("\n");

  return {
    json: {
      ...item.json,
      editPrompt: prompt,
      templateId: bp.templateId,
      templateLabel: bp.templateLabel
    },
    binary: item.binary
  };
});

##########################

**Code in JavaScript - Load static blueprints - backup**

const item = $input.first();

// Three static templates (edit these text blocks anytime)
const blueprints = [
  {
    templateId: "studio_professional",
    templateLabel: "Professional Studio",
    styleBlueprint: [
      "Camera & framing: Eye-level, 70–85mm portrait look; head-and-shoulders; square crop (1:1); centered; clean headroom.",
      "Lighting: soft diffused studio key from front-left; gentle fill; no harsh shadows; catchlights visible.",
      "Background: clean neutral studio background; soft gray or subtle gradient; smooth and distraction-free.",
      "Color & grading: neutral white balance; subtle contrast; photorealistic; natural skin texture."
    ].join("\n")
  },
  {
    templateId: "editorial_natural",
    templateLabel: "Editorial Natural",
    styleBlueprint: [
      "Camera & framing: Eye-level; slightly off-center; head-and-shoulders; square crop (1:1); natural composition.",
      "Lighting: natural window-light look; soft directional light; gentle falloff; flattering but realistic shadows.",
      "Background: softly blurred real-world neutral background; no readable text or branding.",
      "Color & grading: warm editorial tone; mild filmic contrast; clean modern finish; natural skin texture."
    ].join("\n")
  },
  {
    templateId: "executive_dark",
    templateLabel: "Executive Dark",
    styleBlueprint: [
      "Camera & framing: Eye-level; strong centered composition; head-and-shoulders; square crop (1:1); authoritative framing.",
      "Lighting: dramatic but realistic key light; controlled contrast; subtle rim light; professional executive portrait lighting.",
      "Background: dark neutral or charcoal background; clean and distraction-free.",
      "Color & grading: rich contrast; neutral-to-cool executive tone; photorealistic; natural skin texture."
    ].join("\n")
  }
];

return [{
  json: {
    ...item.json,
    blueprints
  },
  binary: item.binary // ✅ keep uploaded photo + logo binaries
}];


###############################



const item = $input.first();

// Three static templates (edit these text blocks anytime)
const blueprints = [
  {
    templateId: "studio_professional",
    templateLabel: "Professional Studio",
    styleBlueprint: [
      "Camera & framing: Eye-level, 70–85mm portrait look; head-and-shoulders; square crop (1:1); centered; clean headroom; add 20px space above head.",
      "Lighting: soft diffused studio key from front-left; gentle fill; no harsh shadows; catchlights visible.",
      "Background: clean neutral studio background; soft gray or subtle gradient; smooth and distraction-free.",
      "Color & grading: neutral white balance; subtle contrast; photorealistic; natural skin texture."
    ].join("\n")
  },
  {
    templateId: "editorial_natural",
    templateLabel: "Editorial Natural",
    styleBlueprint: [
      "Camera & framing: Eye-level; slightly off-center; head-and-shoulders; square crop (1:1); natural composition; add 20px space above head.",
      "Lighting: natural window-light look; soft directional light; gentle falloff; flattering but realistic shadows.",
      "Background: softly blurred real-world neutral background; no readable text or branding.",
      "Color & grading: warm editorial tone; mild filmic contrast; clean modern finish; natural skin texture."
    ].join("\n")
  },
  {
    templateId: "executive_dark",
    templateLabel: "Executive Dark",
    styleBlueprint: [
      "Camera & framing: Eye-level; strong centered composition; head-and-shoulders; square crop (1:1); authoritative framing, add 20px space above head.",
      "Lighting: dramatic but realistic key light; controlled contrast; subtle rim light; professional executive portrait lighting.",
      "Background: dark neutral or charcoal background; clean and distraction-free.",
      "Color & grading: rich contrast; neutral-to-cool executive tone; photorealistic; natural skin texture."
    ].join("\n")
  }
];

return [{
  json: {
    ...item.json,
    blueprints
  },
  binary: item.binary // ✅ keep uploaded photo + logo binaries
}];
