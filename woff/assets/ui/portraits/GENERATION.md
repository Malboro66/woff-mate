# Synthetic portrait generation record

Asset: `portrait.synthetic.aster`

The source image was generated on 2026-09-24 with the built-in OpenAI image
generation tool in ChatGPT Work. No input image, WoFF file, campaign screenshot,
player photograph, historical-person reference, or third-party source image was
used. The generated 1122 × 1402 PNG was center-cropped by one pixel on every
edge to 1120 × 1400, then ancillary metadata was stripped. Pixels were not
resampled or artificially enlarged.

The committed PNG is the canonical source. Image generation is a development
provenance fact, not a production dependency or a reproducible runtime action.
The exact committed bytes are pinned by `SHA256SUMS`.

## Generation prompt

```text
Use case: historical-scene
Asset type: canonical synthetic pilot portrait master for a desktop application's read-only Pilot Dossier fixture
Primary request: Create one high-quality, photorealistic portrait of a completely invented early-20th-century adult aircrew subject. The person must not resemble any identifiable real, famous, or historical individual.
Scene/backdrop: Quiet, low-information neutral studio backdrop with subtle period photographic atmosphere; no recognizable location or campaign context.
Subject: One invented adult, calm neutral expression, direct or slightly off-camera gaze, head and upper torso/bust visible. Androgynous presentation is welcome. Wear a plain dark period-plausible flying coat or civilian high-collared outerwear and an unmarked plain scarf. No visible military uniform insignia.
Style/medium: Restrained monochrome with gentle warm sepia tonality, historically plausible photographic texture, realistic skin and fabric detail, low-to-moderate contrast, subtle natural grain, clear facial readability.
Composition/framing: Vertical portrait. Compose for a final 4:5 crop. Keep the entire head, hair, ears, neck, shoulders, and upper torso inside a central crop-safe area. Stable eye line at approximately 38% from the top, sufficient headroom, shoulders remain safely visible in narrower compact crops. Symmetric or near-symmetric centered framing.
Lighting/mood: Soft diffuse studio/key light, modest shadow detail, dignified and documentary, not dramatic.
Text: none.
Constraints: no text, letters, numbers, nameplates, labels, watermark, signature, borders, frames, flags, maps, readable papers, documents, aircraft, serials, squadron markings, banners, unit signs, rank insignia, cap badges, medals, ribbons, decorations, victory markings, weapons, injuries, campaign scenery, modern styling, strong vignette, fake archival damage, scratches, torn edges, burned corners, stains, handwriting, grunge, excessive blur, saturated color, or decorative props. Do not imitate or reproduce a real person.
```

## Rights and redistribution

The image is synthetic output created for this repository. OpenAI's applicable
terms assign its interest in output to the user to the extent permitted by law.
The repository distributes the committed output under its MIT license. There is
no third-party source asset, required attribution, or separate notice file.
Synthetic output may not be unique, and this record does not make an identity,
historical-authenticity, or exclusivity claim.
