param(
  [Parameter(Mandatory=$true)][string]$RoomId,
  [string]$PhotoPath = "",
  [string]$Terror = "",
  [string]$ExigenciaFisica = "",
  [ValidateSet("", "obra-maestra", "imprescindible", "muy-recomendado", "recomendado", "con-matices", "prescindible")][string]$Seal = "",
  [string]$Aparcamiento = "",
  [string]$AireAcondicionado = "",
  [ValidateRange(-100,100)][double]$PhotoX = 0,
  [ValidateRange(-100,100)][double]$PhotoY = 0,
  [ValidateRange(1,2.5)][double]$PhotoZoom = 1,
  [ValidateRange(-100,100)][double]$CoverX = 0,
  [ValidateRange(-100,100)][double]$CoverY = 0,
  [ValidateRange(1,2.5)][double]$CoverZoom = 1,
  [ValidateSet("auto", "standard", "terror")][string]$ClosingMode = "auto",
  [string]$SynopsisText = "",
  [string]$ReviewText = "",
  [string]$VerdictText = "",
  [ValidateRange(0,4)][int]$OnlySlide = 0,
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $OutputDir) { $OutputDir = Join-Path $root "marketing\exports\carousel" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$script:MarketingFontCollection = [System.Drawing.Text.PrivateFontCollection]::new()
$oswaldPath = Join-Path $root "marketing\fonts\oswald\Oswald-Variable.ttf"
if (Test-Path $oswaldPath) { $script:MarketingFontCollection.AddFontFile($oswaldPath) }

function Normalize([string]$value) {
  if ($null -eq $value) { return "" }
  $text = $value.ToLowerInvariant().Normalize([Text.NormalizationForm]::FormD)
  $sb = [Text.StringBuilder]::new()
  foreach ($ch in $text.ToCharArray()) {
    if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch) -ne [Globalization.UnicodeCategory]::NonSpacingMark) { [void]$sb.Append($ch) }
  }
  return ([regex]::Replace($sb.ToString(), "[^a-z0-9]+", "-")).Trim("-")
}
function Load-Json($path) { Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Font($name, $size, $style = [System.Drawing.FontStyle]::Regular) {
  try {
    $privateFamily = $script:MarketingFontCollection.Families | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if ($privateFamily) { return [System.Drawing.Font]::new($privateFamily, $size, $style, [System.Drawing.GraphicsUnit]::Pixel) }
    return [System.Drawing.Font]::new($name, $size, $style, [System.Drawing.GraphicsUnit]::Pixel)
  }
  catch { return [System.Drawing.Font]::new("Arial", $size, $style, [System.Drawing.GraphicsUnit]::Pixel) }
}
function Draw-CoverCrop($g, $image, $rect, [double]$focalX = 0, [double]$focalY = 0, [double]$zoom = 1) {
  $scale = [Math]::Max($rect.Width / $image.Width, $rect.Height / $image.Height) * $zoom
  $srcW = [Math]::Max(1,[int]($rect.Width / $scale)); $srcH = [Math]::Max(1,[int]($rect.Height / $scale))
  $availableX = [Math]::Max(0,$image.Width - $srcW); $availableY = [Math]::Max(0,$image.Height - $srcH)
  $normalizedX = ([Math]::Max(-100,[Math]::Min(100,$focalX)) + 100) / 200
  $normalizedY = ([Math]::Max(-100,[Math]::Min(100,$focalY)) + 100) / 200
  $srcX = [int]($availableX * $normalizedX); $srcY = [int]($availableY * $normalizedY)
  $g.DrawImage($image, $rect, [System.Drawing.Rectangle]::new($srcX,$srcY,$srcW,$srcH), [System.Drawing.GraphicsUnit]::Pixel)
}
function Text($g, [string]$value, $font, $brush, $rect, $align = "Near") {
  $fmt = [System.Drawing.StringFormat]::new()
  $fmt.Alignment = [System.Drawing.StringAlignment]::$align
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::Near
  $fmt.Trimming = [System.Drawing.StringTrimming]::EllipsisWord
  $g.DrawString($value, $font, $brush, $rect, $fmt)
  $fmt.Dispose()
}
function CenteredText($g, [string]$value, $font, $brush, $rect) {
  $fmt = [System.Drawing.StringFormat]::new()
  $fmt.Alignment = [System.Drawing.StringAlignment]::Center
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
  $fmt.Trimming = [System.Drawing.StringTrimming]::EllipsisCharacter
  $g.DrawString($value, $font, $brush, $rect, $fmt)
  $fmt.Dispose()
}
function FittedCenteredText($g, [string]$value, [string]$fontName, [int]$maxSize, [int]$minSize, $style, $brush, $shadowBrush, $rect) {
  $fmt = [System.Drawing.StringFormat]::new()
  $fmt.Alignment = [System.Drawing.StringAlignment]::Center
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
  $fmt.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
  $fmt.Trimming = [System.Drawing.StringTrimming]::EllipsisCharacter
  $selectedFont = $null
  for ($size = $maxSize; $size -ge $minSize; $size--) {
    $candidate = Font $fontName $size $style
    $measured = $g.MeasureString($value, $candidate)
    if ($measured.Width -le ($rect.Width - 20) -or $size -eq $minSize) {
      $selectedFont = $candidate
      break
    }
    $candidate.Dispose()
  }
  $shadowRect = [Drawing.RectangleF]::new($rect.X + 1, $rect.Y + 1, $rect.Width, $rect.Height)
  $g.DrawString($value, $selectedFont, $shadowBrush, $shadowRect, $fmt)
  $g.DrawString($value, $selectedFont, $brush, $rect, $fmt)
  $selectedFont.Dispose()
  $fmt.Dispose()
}
function FittedParagraph($g, [string]$value, [string]$fontName, [int]$maxSize, [int]$minSize, $style, $brush, $rect) {
  $value = [regex]::Replace($value.Trim(), "\s+", " ")
  $fmt = [System.Drawing.StringFormat]::new()
  $fmt.Alignment = [System.Drawing.StringAlignment]::Near
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::Near
  $fmt.Trimming = [System.Drawing.StringTrimming]::EllipsisWord
  $selectedFont = $null
  for ($size = $maxSize; $size -ge $minSize; $size--) {
    $candidate = Font $fontName $size $style
    $measured = $g.MeasureString($value, $candidate, [Drawing.SizeF]::new($rect.Width, 10000), $fmt)
    if ($measured.Height -le ($rect.Height - 8) -or $size -eq $minSize) {
      $selectedFont = $candidate
      break
    }
    $candidate.Dispose()
  }
  $g.DrawString($value, $selectedFont, $brush, $rect, $fmt)
  $selectedFont.Dispose()
  $fmt.Dispose()
}
function Short([string]$value, [int]$max = 260) {
  $value = ([regex]::Replace(($value -replace "\s+", " ").Trim(), "[\r\n]+", " "))
  if ($value.Length -le $max) { return $value }
  return $value.Substring(0, $max).TrimEnd() + "..."
}
function SynopsisExcerpt([string]$value, [int]$max = 620) {
  $value = [regex]::Replace($value.Trim(), "\s+", " ")
  if ($value.Length -le $max) { return $value }
  $candidate = $value.Substring(0, $max)
  $lastStop = [Math]::Max($candidate.LastIndexOf("."), [Math]::Max($candidate.LastIndexOf("!"), $candidate.LastIndexOf("?")))
  if ($lastStop -ge [int]($max * 0.65)) { return $candidate.Substring(0, $lastStop + 1) }
  $lastSpace = $candidate.LastIndexOf(" ")
  if ($lastSpace -gt 0) { $candidate = $candidate.Substring(0, $lastSpace) }
  return $candidate.TrimEnd() + "..."
}
function SealLabel([string]$seal) {
  switch ($seal) {
    "obra-maestra" { return "OBRA MAESTRA" }
    "imprescindible" { return "IMPRESCINDIBLE" }
    "muy-recomendado" { return "MUY RECOMENDADO" }
    "recomendado" { return "RECOMENDADO" }
    "con-matices" { return "CON MATICES" }
    "prescindible" { return "PRESCINDIBLE" }
    default { return "" }
  }
}
function Is-TerrorRoom($room, $review) {
  if($room.terror -eq $true){return $true}
  $terrorFlag=([string]$room.terror).Trim().ToLowerInvariant()
  if($terrorFlag -in @("true","1","si","yes")){return $true}
  $signals=Normalize (([string]$room.nombre) + " " + ([string]$room.tematica) + " " + ([string]$room.tipo) + " " + ([string]$review.tematica) + " " + ([string]$review.tipo))
  return $signals -match '(terror|horror|exorcis|posesion|paranormal|miedo)'
}
function Draw-StyledSynopsis($g, [string]$value, $rect, $bodyBrush, $introBrush) {
  $value = SynopsisExcerpt $value 620
  $intro = ""
  $body = $value
  $match = [regex]::Match($value, '^.*?[.!?](?:\s|$)')
  if ($match.Success -and $match.Value.Length -lt ($value.Length - 20)) {
    $intro = $match.Value.Trim()
    $body = $value.Substring($match.Length).Trim()
  }
  if (-not $intro) {
    FittedParagraph $g $body "Oswald" 19 15 ([System.Drawing.FontStyle]::Regular) $bodyBrush $rect
    return
  }

  $introFont = Font "Oswald Medium" 19 ([System.Drawing.FontStyle]::Regular)
  $introFormat = [System.Drawing.StringFormat]::new()
  $introFormat.Alignment = [System.Drawing.StringAlignment]::Near
  $introFormat.LineAlignment = [System.Drawing.StringAlignment]::Near
  $introFormat.Trimming = [System.Drawing.StringTrimming]::Word
  $introSize = $g.MeasureString($intro, $introFont, [Drawing.SizeF]::new($rect.Width, 1000), $introFormat)
  $introHeight = [Math]::Ceiling($introSize.Height) + 2
  $introRect = [Drawing.RectangleF]::new($rect.X, $rect.Y, $rect.Width, $introHeight)
  $g.DrawString($intro, $introFont, $introBrush, $introRect, $introFormat)
  $introFont.Dispose(); $introFormat.Dispose()

  $bodyY = $rect.Y + $introHeight + 8
  $bodyRect = [Drawing.RectangleF]::new($rect.X, $bodyY, $rect.Width, ($rect.Bottom - $bodyY))
  FittedParagraph $g $body "Oswald" 18 15 ([System.Drawing.FontStyle]::Regular) $bodyBrush $bodyRect
}
function Save-Slide([string]$path, [string]$kicker, [string]$title, [string]$body, [string]$footer) {
  $bmp = [System.Drawing.Bitmap]::new(1080,1080)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.Clear([System.Drawing.Color]::FromArgb(9,10,15))
  $border = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(125,187,63), 3)
  $g.DrawRectangle($border, 34, 34, 1012, 1012); $border.Dispose()
  $green = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(132,201,79))
  $white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(236,236,242))
  $muted = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(157,160,180))
  $amber = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(246,166,25))
  $g.DrawString("THE VAULT ESCAPE", (Font "Consolas" 25), $green, 68, 70)
  Text $g $kicker.ToUpperInvariant() (Font "Consolas" 24) $amber ([Drawing.RectangleF]::new(68,150,944,42)) "Center"
  Text $g $title.ToUpperInvariant() (Font "Arial Black" 62) $white ([Drawing.RectangleF]::new(80,230,920,150)) "Center"
  Text $g $body (Font "Arial" 35) $muted ([Drawing.RectangleF]::new(115,430,850,370)) "Center"
  Text $g $footer.ToUpperInvariant() (Font "Consolas" 24) $green ([Drawing.RectangleF]::new(80,920,920,55)) "Center"
  $g.Dispose(); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  $green.Dispose();$white.Dispose();$muted.Dispose();$amber.Dispose()
}
function Save-PhotoSlide([string]$path, [string]$title, [string]$photoPath) {
  $bmp = [System.Drawing.Bitmap]::new(1080,1080)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.Clear([System.Drawing.Color]::FromArgb(9,10,15))
  $border = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(125,187,63), 3)
  $g.DrawRectangle($border, 34, 34, 1012, 1012); $border.Dispose()
  $image = [System.Drawing.Image]::FromFile($photoPath)
  $dest = [System.Drawing.Rectangle]::new(90,170,900,700)
  $scale = [Math]::Min($dest.Width / $image.Width, $dest.Height / $image.Height)
  $width = [int]($image.Width * $scale); $height = [int]($image.Height * $scale)
  $x = $dest.X + [int](($dest.Width - $width) / 2); $y = $dest.Y + [int](($dest.Height - $height) / 2)
  $g.DrawImage($image, [System.Drawing.Rectangle]::new($x,$y,$width,$height)); $image.Dispose()
  $green = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(132,201,79))
  $white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(236,236,242))
  Text $g "FOTOS DEL GRUPO" (Font "Consolas" 24) $green ([Drawing.RectangleF]::new(68,90,944,42)) "Center"
  Text $g $title.ToUpperInvariant() (Font "Arial Black" 43) $white ([Drawing.RectangleF]::new(70,900,940,70)) "Center"
  $g.Dispose(); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $green.Dispose(); $white.Dispose()
}
function Save-ScoreTemplate([string]$path, $templatePath, $photoPath, $review, $room, [string]$terror, [string]$physical, [string]$seal, [string]$parking, [string]$ac, [double]$photoX, [double]$photoY, [double]$photoZoom) {
  $template = [System.Drawing.Image]::FromFile($templatePath)
  $photo = [System.Drawing.Image]::FromFile($photoPath)
  $bmp = [System.Drawing.Bitmap]::new($template.Width, $template.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $g.Clear([System.Drawing.Color]::FromArgb(5,7,8))
  # The opening is wider than its central visible area; extend beneath the
  # irregular frame so the photograph remains centered and no white strip leaks.
  $photoRect = [System.Drawing.Rectangle]::new(400,105,510,800)
  Draw-CoverCrop $g $photo $photoRect $photoX $photoY $photoZoom
  $overlay = [System.Drawing.Bitmap]::new($template.Width,$template.Height,[System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $og = [System.Drawing.Graphics]::FromImage($overlay); $og.DrawImage($template,0,0,$template.Width,$template.Height); $og.Dispose()
  for($y=$photoRect.Top;$y -lt $photoRect.Bottom;$y++){ for($x=$photoRect.Left;$x -lt $photoRect.Right;$x++){ $px=$overlay.GetPixel($x,$y); if($px.R -gt 228 -and $px.G -gt 228 -and $px.B -gt 228){$overlay.SetPixel($x,$y,[System.Drawing.Color]::FromArgb(0,$px.R,$px.G,$px.B))} } }
  $g.DrawImage($overlay,0,0,$template.Width,$template.Height)
  if($seal){
    $sealPath=Join-Path $root ("marketing\templates\seals\{0}.jpg" -f $seal)
    if(Test-Path $sealPath){
      $sealImage=[System.Drawing.Image]::FromFile($sealPath)
      $sealState=$g.Save()
      $sealMask=[System.Drawing.Drawing2D.GraphicsPath]::new()
      $sealMask.AddEllipse([System.Drawing.Rectangle]::new(88,758,195,200))
      $g.SetClip($sealMask,[System.Drawing.Drawing2D.CombineMode]::Intersect)
      $g.DrawImage($sealImage,[System.Drawing.Rectangle]::new(78,754,215,215))
      $g.Restore($sealState)
      $sealMask.Dispose()
      $sealImage.Dispose()
    }
  }
  $white=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(245,245,240)); $green=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(132,201,79)); $amber=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(246,166,25)); $scoreGold=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255,198,35)); $dataGreen=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(183,235,134)); $dark=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(8,10,12)); $scoreShadow=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(210,0,0,0))
  $scoreFont=Font "Stencil" 23 ([System.Drawing.FontStyle]::Bold); $small=Font "Arial" 19
  $scores=@($review.historia,$review.ambientacion,$review.jugabilidad,$review.gamemaster,$terror,$physical)
  # Measured optical centers of the six slanted score boxes in the template.
  $ys=@(307,374,442,509,577,644)
  for($i=0;$i -lt 6;$i++){
    $value=if($scores[$i]){[string]$scores[$i]}else{"-"}
    if($value -match '^(\d+)[\.,]0+$'){$value=$matches[1]}
    $scoreBrush=if($value -eq "10"){$scoreGold}else{$white}
    CenteredText $g $value $scoreFont $scoreShadow ([Drawing.RectangleF]::new(276,$ys[$i]+2,68,46))
    CenteredText $g $value $scoreFont $scoreBrush ([Drawing.RectangleF]::new(274,$ys[$i],68,46))
  }
  $duration=if($room.duracion){"$($room.duracion) min"}else{"-"}; $type=if($review.tipo){[string]$review.tipo}elseif($room.tipo){[string]$room.tipo}elseif($room.tematica){[string]$room.tematica}else{"-"}
  $dataStyle=[System.Drawing.FontStyle]::Regular
  FittedCenteredText $g $duration "Bahnschrift SemiBold Condensed" 22 16 $dataStyle $dataGreen $scoreShadow ([Drawing.RectangleF]::new(245,1031,210,40))
  FittedCenteredText $g $type "Bahnschrift SemiBold Condensed" 22 15 $dataStyle $dataGreen $scoreShadow ([Drawing.RectangleF]::new(665,1031,210,40))
  $parkingText=$(if($parking){$parking}else{"No indicado"}); $acText=$(if($ac){$ac}else{"No indicado"})
  FittedCenteredText $g $parkingText "Bahnschrift SemiBold Condensed" 21 14 $dataStyle $dataGreen $scoreShadow ([Drawing.RectangleF]::new(235,1121,230,40))
  FittedCenteredText $g $acText "Bahnschrift SemiBold Condensed" 21 14 $dataStyle $dataGreen $scoreShadow ([Drawing.RectangleF]::new(655,1121,230,40))
  $g.Dispose(); $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $template.Dispose();$photo.Dispose();$overlay.Dispose();$white.Dispose();$green.Dispose();$amber.Dispose();$scoreGold.Dispose();$dataGreen.Dispose();$dark.Dispose();$scoreShadow.Dispose();$scoreFont.Dispose();$small.Dispose()
}
function Save-HistoryTemplate([string]$path, $templatePath, $coverPath, [string]$synopsis, [double]$coverX, [double]$coverY, [double]$coverZoom) {
  $template = [System.Drawing.Image]::FromFile($templatePath)
  $cover = [System.Drawing.Image]::FromFile($coverPath)
  $bmp = [System.Drawing.Bitmap]::new($template.Width, $template.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $g.Clear([System.Drawing.Color]::FromArgb(5,7,8))

  $photoRect = [System.Drawing.Rectangle]::new(440,205,480,715)
  Draw-CoverCrop $g $cover $photoRect $coverX $coverY $coverZoom

  $overlay = [System.Drawing.Bitmap]::new($template.Width,$template.Height,[System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $og = [System.Drawing.Graphics]::FromImage($overlay)
  $og.DrawImage($template,0,0,$template.Width,$template.Height)
  $og.Dispose()
  for($y=$photoRect.Top;$y -lt $photoRect.Bottom;$y++){
    for($x=$photoRect.Left;$x -lt $photoRect.Right;$x++){
      $px=$overlay.GetPixel($x,$y)
      if($px.R -gt 228 -and $px.G -gt 228 -and $px.B -gt 228){$overlay.SetPixel($x,$y,[System.Drawing.Color]::FromArgb(0,$px.R,$px.G,$px.B))}
    }
  }
  $g.DrawImage($overlay,0,0,$template.Width,$template.Height)

  $textBrush=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(232,234,226))
  $introBrush=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(167,225,91))
  Draw-StyledSynopsis $g $synopsis ([Drawing.RectangleF]::new(62,426,335,450)) $textBrush $introBrush

  $g.Dispose(); $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $template.Dispose(); $cover.Dispose(); $overlay.Dispose(); $textBrush.Dispose(); $introBrush.Dispose()
}
function Save-ReviewTemplate([string]$path, $templatePath, $review, $room, [string]$seal, [string]$reviewOverride, [string]$verdictOverride) {
  $template = [System.Drawing.Image]::FromFile($templatePath)
  $bmp = [System.Drawing.Bitmap]::new($template.Width, $template.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $g.DrawImage($template,0,0,$template.Width,$template.Height)

  $rawReview = if($reviewOverride){$reviewOverride}else{[string]$review.descripcion}
  $verdict = $verdictOverride
  $verdictMatch = [regex]::Match($rawReview, '(?is)(?:Veredicto\s+The\s+Vault)\s*(.+)$')
  if($verdictMatch.Success){
    if(-not $verdict){$verdict = $verdictMatch.Groups[1].Value.Trim()}
    $rawReview = $rawReview.Substring(0,$verdictMatch.Index)
  }
  $locationPin = [char]::ConvertFromUtf32(0x1F4CD)
  $infoIndex = $rawReview.IndexOf($locationPin)
  if($infoIndex -gt 0){$rawReview = $rawReview.Substring(0,$infoIndex)}
  $rawReview = [regex]::Replace($rawReview, '\p{So}', '')
  $reviewExcerpt = SynopsisExcerpt $rawReview 760
  $verdictExcerpt = if($verdict){SynopsisExcerpt ([regex]::Replace($verdict, '\p{So}', '')) 260}else{"Consulta la review completa en thevaultescape.com"}
  $category = SealLabel $seal

  $green=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(167,225,91))
  $white=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(235,236,230))
  $muted=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(181,185,174))
  $shadow=[System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(210,0,0,0))
  $line=[System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(120,167,225,91),2)

  FittedCenteredText $g ([string]$room.nombre).ToUpperInvariant() "Oswald SemiBold" 31 22 ([System.Drawing.FontStyle]::Regular) $white $shadow ([Drawing.RectangleF]::new(90,405,780,48))
  $meta = (([string]$room.empresa) + " - " + ([string]$room.ciudad)).ToUpperInvariant()
  FittedCenteredText $g $meta "Oswald Medium" 18 14 ([System.Drawing.FontStyle]::Regular) $green $shadow ([Drawing.RectangleF]::new(100,454,760,30))
  $g.DrawLine($line,105,498,855,498)
  FittedParagraph $g $reviewExcerpt "Oswald" 21 16 ([System.Drawing.FontStyle]::Regular) $white ([Drawing.RectangleF]::new(112,520,736,305))
  $g.DrawLine($line,105,844,855,844)
  $verdictTitle = if($category){"VEREDICTO THE VAULT - $category"}else{"VEREDICTO THE VAULT"}
  FittedCenteredText $g $verdictTitle "Oswald SemiBold" 20 15 ([System.Drawing.FontStyle]::Regular) $green $shadow ([Drawing.RectangleF]::new(135,854,690,34))
  FittedParagraph $g $verdictExcerpt "Oswald" 18 14 ([System.Drawing.FontStyle]::Regular) $muted ([Drawing.RectangleF]::new(145,897,670,105))

  $g.Dispose(); $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $template.Dispose(); $green.Dispose(); $white.Dispose(); $muted.Dispose(); $shadow.Dispose(); $line.Dispose()
}
function Save-TemplateSlide([string]$path, $templatePath) {
  $template=[System.Drawing.Image]::FromFile($templatePath)
  $bmp=[System.Drawing.Bitmap]::new($template.Width,$template.Height,[System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.DrawImage($template,0,0,$template.Width,$template.Height)
  $g.Dispose(); $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $template.Dispose()
}

$catalog = Load-Json (Join-Path $root "catalog.json")
$rooms = @($catalog.catalogo)
$key = Normalize $RoomId
$room = $rooms | Where-Object { (Normalize $_.id) -eq $key -or (Normalize $_.nombre) -eq $key } | Select-Object -First 1
if (-not $room) { throw "Sala no encontrada: $RoomId" }
$published = Load-Json (Join-Path $root "published_reviews.json")
$review = $null
foreach ($prop in $published.reviews.PSObject.Properties) {
  if ((Normalize $prop.Name) -eq (Normalize $room.id) -or (Normalize $prop.Value.roomName) -eq (Normalize $room.nombre)) { $review = $prop.Value.review; break }
}
if (-not $review) { throw "La sala no tiene review publicada: $($room.nombre)" }
$reviewText = [string]$review.descripcion
if (-not $Aparcamiento -and $reviewText -match '(?i)Aparcamiento\s*:\s*([^\r\n.]+)') { $Aparcamiento = $matches[1].Trim() }
if (-not $AireAcondicionado -and $reviewText -match '(?i)(?:Aire acondicionado|Local climatizado)\s*:\s*([^\r\n.]+)') { $AireAcondicionado = $matches[1].Trim() }
$photosPayload = Load-Json (Join-Path $root "review_photos.json")
$reviewPhoto = $null
foreach ($prop in $photosPayload.photos.PSObject.Properties) {
  if ((Normalize $prop.Name) -eq (Normalize $room.id) -or (Normalize $prop.Value.room) -eq (Normalize $room.nombre)) {
    $candidate = @($prop.Value.photos | Where-Object { $_.src } | Select-Object -Skip 1 -First 1)
    if ($candidate) { $reviewPhoto = Join-Path $root ($candidate[0].src -replace "/", "\") }
    break
  }
}
$photoResolved = $null
if ($PhotoPath) { $photoResolved = if ([IO.Path]::IsPathRooted($PhotoPath)) { $PhotoPath } else { Join-Path $root ($PhotoPath -replace "/", "\") } }
if (-not $photoResolved -or -not (Test-Path $photoResolved)) { $photoResolved = $reviewPhoto }
if (-not $photoResolved -or -not (Test-Path $photoResolved)) { $photoResolved = Join-Path $root (($room.imagen -replace "/", "\")) }
if (-not $photoResolved -or -not (Test-Path $photoResolved)) { throw "No se encuentra una foto para la sala: $($room.nombre)" }

$name = [string]($room.nombre)
$city = [string]($room.ciudad)
$company = [string]($room.empresa)
$rating = if ($review.valoracion) { [string]$review.valoracion } elseif ($room.rating) { [string]$room.rating } else { "-" }
$players = if ($room.min_personas -and $room.max_personas) { "$($room.min_personas)-$($room.max_personas) jugadores" } else { "Equipo escapista" }
$duration = if ($room.duracion) { "$($room.duracion) minutos" } else { "Duracion variable" }
$slug = Normalize $name
$coverScript = Join-Path $root "scripts\generate_marketing_template.ps1"
$coverArgs = @("-RoomId",$RoomId,"-Template","review-square","-Fit","smart","-OutputDir",$OutputDir)
if ($PhotoPath) { $coverArgs += @("-PhotoPath",$PhotoPath) }
$coverPath = Join-Path $OutputDir ("{0}-01-portada.png" -f $slug)
$scoreTemplate = Join-Path $root "marketing\templates\carousel-01-score.jpg"
if($OnlySlide -in @(0,1)){
  if ((Test-Path $scoreTemplate) -and (Test-Path $photoResolved)) {
    Save-ScoreTemplate $coverPath $scoreTemplate $photoResolved $review $room $Terror $ExigenciaFisica $Seal $Aparcamiento $AireAcondicionado $PhotoX $PhotoY $PhotoZoom
  } else {
    $coverJson = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $coverScript @coverArgs | Out-String | ConvertFrom-Json
    Copy-Item -LiteralPath (Join-Path $root ($coverJson.output -replace "/", "\")) -Destination $coverPath -Force
  }
}

$p2 = Join-Path $OutputDir ("{0}-02-datos.png" -f $slug)
$p3 = Join-Path $OutputDir ("{0}-03-opinion.png" -f $slug)
$p4 = Join-Path $OutputDir ("{0}-04-cierre.png" -f $slug)
$historyTemplate = Join-Path $root "marketing\templates\carousel-02-history.jpg"
$roomCover = if($room.imagen){Join-Path $root (([string]$room.imagen) -replace "/", "\")}else{$null}
$socialSynopsis=if($SynopsisText){$SynopsisText}else{[string]$room.descripcion}
if($OnlySlide -in @(0,2)){
  if((Test-Path $historyTemplate) -and $roomCover -and (Test-Path $roomCover) -and $socialSynopsis){
    Save-HistoryTemplate $p2 $historyTemplate $roomCover $socialSynopsis $CoverX $CoverY $CoverZoom
  } else {
    Save-Slide $p2 "La ficha" $name "$company`n$city`n`n$duration`n$players`n`nValoracion del grupo: $rating / 10" "Desliza para conocer la experiencia"
  }
}
$reviewTemplate = Join-Path $root "marketing\templates\carousel-03-review.jpg"
if($OnlySlide -in @(0,3)){
  if(Test-Path $reviewTemplate){
    Save-ReviewTemplate $p3 $reviewTemplate $review $room $Seal $ReviewText $VerdictText
  } else {
    Save-Slide $p3 "La opinion del grupo" "Lo que vivimos" (Short ([string]$review.descripcion) 320) "Review completa en thevaultescape.com"
  }
}
$useTerrorClosing=if($ClosingMode -eq "terror"){$true}elseif($ClosingMode -eq "standard"){$false}else{Is-TerrorRoom $room $review}
$closingTemplate = if($useTerrorClosing){Join-Path $root "marketing\templates\carousel-04-terror.jpg"}else{Join-Path $root "marketing\templates\carousel-04-standard.jpg"}
if($OnlySlide -in @(0,4)){
  if(Test-Path $closingTemplate){
    Save-TemplateSlide $p4 $closingTemplate
  } else {
    Save-Slide $p4 "Tu proxima mision" "Descubre tu siguiente escape" "Busca, compara y guarda tus salas favoritas en nuestra web." "thevaultescape.com"
  }
}
$slides = @($coverPath,$p2,$p3,$p4)

$rootText = ([string]$root).TrimEnd("\")
$relative = @($slides | ForEach-Object { $_.Substring($rootText.Length).TrimStart("\").Replace("\","/") })
$script:MarketingFontCollection.Dispose()
@{ ok=$true; room_id=$room.id; room_name=$name; template="review-carousel"; slides=$relative; output=$relative -join ", "; output_path=$slides[0] } | ConvertTo-Json -Depth 5
