# Image enhancement notes

## What the literature supports

Microscopy enhancement usually addresses a specific failure mode rather than applying one
universal filter:

- Flat-field or background correction removes illumination gradients and vignetting. Sequence-based
  estimates are more reliable than single-frame estimates. BaSiC models both multiplicative shading
  and additive dark-field effects. The PlanktoScope and Zimmerman plankton pipelines use running or
  sampled median backgrounds before segmentation.
- Local contrast enhancement makes weak structures easier to see when illumination varies across a
  frame. CLAHE limits the noise amplification associated with ordinary adaptive histogram
  equalization, but strong settings can still amplify microscopy noise.
- Mild unsharp masking improves the visibility of fine boundaries. It does not restore lost optical
  resolution and strong settings can create halos.
- Deconvolution can recover shape when the microscope point spread function is known or modeled.
  This is more defensible than generic sharpening for quantitative restoration, but it needs an
  optical model and is not suitable as an instant generic preset.
- Better acquisition can outperform post-processing. Defocus, phase contrast, DIC, coherent
  illumination, and staining physically convert otherwise weak phase differences into visible
  intensity differences.

## Product decision

The live pane uses reversible parameter presets built from global tone controls, CLAHE on LAB
luminance, monochrome conversion, and mild unsharp masking. It does not include deconvolution or
learned enhancement because those require calibration or may create unsupported detail.

Enhancement is currently part of the capture pipeline. It therefore changes preview, clip, snapshot,
and detector pixels. Natural is the unprocessed reference preset.

## Sources

- Pollina et al. (2022), PlanktoScope, doi:10.3389/fmars.2022.949428. Local copy:
  `fmars-09-949428.pdf`.
- Zimmerman et al. (2020), Embedded System to Detect, Track and Classify Plankton Using a Lensless
  Video Microscope, arXiv:2005.13064. Local copy: `2005.13064v1.pdf`.
- Peng et al. (2017), BaSiC background and shading correction:
  https://doi.org/10.1038/ncomms14836
- Stimper et al. (2019), multidimensional CLAHE:
  https://doi.org/10.1109/ACCESS.2019.2952899
- Gutiérrez-Medina and Sánchez Miranda (2017), quantitative bright-field restoration:
  https://doi.org/10.1016/j.bpj.2017.09.002
- Yin, Kanade, and Chen (2012), phase contrast restoration for segmentation:
  https://doi.org/10.1016/j.media.2011.12.006
- Model and Burkhardt (2001), contrast from bright-field focus stacks:
  https://doi.org/10.1002/1097-0029(20010201)52:3%3C245::AID-JEMT1002%3E3.0.CO;2-6
