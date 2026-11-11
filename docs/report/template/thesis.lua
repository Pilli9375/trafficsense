--[[
Pandoc filter (DOCX) for the TrafficSense thesis in the college capstone format
(docs/report/format_spec.md). scripts/build_report.py runs it before --citeproc.

Numbering
* Chapters are the level-1 headers without .unnumbered: CHAPTER 1, 2, ... Sections n.m (level 2)
  and n.m.k (level 3) are numbered; level 4 becomes an unnumbered bold heading ("Minor Heading")
  and a reference to it gives its parent's number.
* Figures are numbered continuously through the report: Figure 1, 2, ... Tables per chapter:
  Table c.n. Both captions carry Word SEQ fields (the cached result is the number), so Word's
  lists of figures and tables collect them; the first table of a chapter restarts with \r 1
  (LibreOffice ignores SEQ's \s switch).
* A caption's title (Caption style, in the lists) is its short="..." attribute or else its first
  sentence; the caption text follows in "Caption Note" style (all of it when short= is given,
  the rest otherwise), so no caption text is lost.
* Cross-references written as citations: @fig:x -> "Figure 12", @tbl:x -> "Table 4.2",
  @sec:x -> "Chapter 4" / "Section 2.2.1"; [-@fig:x] gives the bare number. The numbers are
  written to $REPORT_NUMBERS_JSON for the build's checks.

Contents
* Every chapter, section, subsection and the unnumbered front headings get a hidden TC field;
  the contents is a TOC field built from them (TOC \f \l "1-3"), so chapter entries read
  "1 Introduction" even though the heading itself has two lines (CHAPTER 1 / INTRODUCTION).
  Classes: .notoc = no contents entry.
* The fields are written with a marker result (@@TOC@@, @@LOT@@, @@LOF@@) that the build
  replaces with the real entries and page numbers; the format check fails if one is left.

Blocks
* div .lists: TABLE OF CONTENTS, LIST OF TABLES, LIST OF FIGURES. div .frontmatter-end: the
  section break that ends the roman-numbered front matter (the build adds the footers).
* div .thesis-logo: the university logo (path in metadata `logo`, taken from the college format
  file at build time). div .biodata name= reg= email= [mobile= address= photo=]: one biodata page (the optional attributes are
  the private details of a personal build, see src/trafficsense/report/biodata.py; without them the page has
  blank lines and an empty photo box, which is what the public report shows). div .note-page: the
  closing NOTE page. span .tab: a tab (to the right tab stop of the paragraph style).
* div .code-listings is replaced by the build with generated listings before pandoc runs.
]]

local stringify = pandoc.utils.stringify

local numbers = {}          -- id -> {kind=, num=}

local function esc(s)
  s = s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
  return s
end

local function field(instr, result, hidden)
  local rp = hidden and "<w:rPr><w:vanish/></w:rPr>" or ""
  local x = "<w:r>" .. rp .. '<w:fldChar w:fldCharType="begin"/></w:r><w:r>' .. rp ..
    '<w:instrText xml:space="preserve"> ' .. esc(instr) .. " </w:instrText></w:r>"
  if result then
    x = x .. '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t xml:space="preserve">' ..
      esc(result) .. "</w:t></w:r>"
  end
  return x .. "<w:r>" .. rp .. '<w:fldChar w:fldCharType="end"/></w:r>'
end

local function tc(text, level)
  text = text:gsub('"', "\u{201D}")
  return pandoc.RawInline("openxml", field('TC "' .. text .. '" \\l ' .. level, nil, true))
end

local function styled(style, blocks)
  return pandoc.Div(blocks, pandoc.Attr("", {}, {["custom-style"] = style}))
end

local PAGE_BREAK = pandoc.RawBlock("openxml", '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" ' ..
  'w:lineRule="auto"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>')

-- pass 1: numbers in document order ---------------------------------------------------------
local function number_all(blocks)
  local chap, sec, sub, fig, tbl = 0, 0, 0, 0, 0
  local current = nil      -- number of the innermost numbered section (for level-4 references)
  local function walk(bl)
    for _, b in ipairs(bl) do
      if b.t == "Header" then
        local unnum = b.classes:includes("unnumbered")
        if b.level == 1 then
          if unnum then
            current = nil
          else
            chap = chap + 1; sec = 0; sub = 0; tbl = 0
            b.attributes["number"] = tostring(chap)
            current = {kind = "Chapter", num = tostring(chap)}
            if b.identifier ~= "" then numbers[b.identifier] = current end
          end
        elseif b.level == 2 and not unnum and chap > 0 then
          sec = sec + 1; sub = 0
          b.attributes["number"] = chap .. "." .. sec
          current = {kind = "Section", num = b.attributes["number"]}
          if b.identifier ~= "" then numbers[b.identifier] = current end
        elseif b.level == 3 and not unnum and chap > 0 then
          sub = sub + 1
          b.attributes["number"] = chap .. "." .. sec .. "." .. sub
          current = {kind = "Section", num = b.attributes["number"]}
          if b.identifier ~= "" then numbers[b.identifier] = current end
        elseif b.level >= 4 then
          if b.identifier ~= "" and current then numbers[b.identifier] = current end
        end
      elseif b.t == "Figure" then
        fig = fig + 1
        b.attributes["number"] = tostring(fig)
        if b.identifier ~= "" then numbers[b.identifier] = {kind = "Figure", num = tostring(fig)} end
      elseif b.t == "Div" then
        if b.identifier:match("^tbl:") then
          if chap == 0 then
            io.stderr:write("thesis.lua: table " .. b.identifier .. " outside a chapter\n"); os.exit(1)
          end
          tbl = tbl + 1
          b.attributes["number"] = chap .. "." .. tbl
          b.attributes["seq"] = tostring(tbl)
          numbers[b.identifier] = {kind = "Table", num = b.attributes["number"]}
        end
        walk(b.content)
      end
    end
  end
  walk(blocks)
end

local function ref_inlines(id, bare)
  local x = numbers[id]
  if not x then
    io.stderr:write("thesis.lua: unknown reference " .. id .. "\n")
    os.exit(1)
  end
  return {pandoc.Str((bare and "" or (x.kind .. "\u{00A0}")) .. x.num)}
end

local function is_xref(id) return id:match("^fig:") or id:match("^tbl:") or id:match("^sec:") end

-- captions: first sentence = title ----------------------------------------------------------
local NOT_END = {["e.g."] = true, ["i.e."] = true, ["vs."] = true, ["et"] = true, ["al."] = true,
                 ["approx."] = true, ["Fig."] = true, ["No."] = true}

local function split_caption(blocks)
  local inl = pandoc.List()
  for i, b in ipairs(blocks) do
    if i > 1 then inl:insert(pandoc.Space()) end
    if b.content then inl:extend(b.content) end
  end
  for i, x in ipairs(inl) do
    if x.t == "Str" and x.text:match("%.$") and not NOT_END[x.text] and
       (i == #inl or inl[i + 1].t == "Space" or inl[i + 1].t == "SoftBreak") then
      local title = pandoc.List({table.unpack(inl, 1, i)})
      title[#title] = pandoc.Str(x.text:sub(1, -2))
      local rest = pandoc.List({table.unpack(inl, i + 2)})
      while #rest > 0 and (rest[1].t == "Space" or rest[1].t == "SoftBreak") do rest:remove(1) end
      return title, rest
    end
  end
  return inl, pandoc.List()
end

-- with a short title (attribute short="..."), the whole caption becomes the note below it
local function title_and_note(short, blocks)
  if short and short ~= "" then
    local doc = pandoc.read(short, "markdown")
    local note = pandoc.List()
    for i, b in ipairs(blocks) do
      if i > 1 then note:insert(pandoc.Space()) end
      if b.content then note:extend(b.content) end
    end
    return doc.blocks[1].content, note
  end
  return split_caption(blocks)
end

local function caption_blocks(label, number, instr, title, note, note_style)
  local inl = pandoc.List({pandoc.Str(label .. "\u{00A0}"), pandoc.RawInline("openxml", field(instr, number))})
  if label == "Table" then
    -- "Table 4." + SEQ result "2": the chapter part is plain text, the field counts in the chapter
    inl = pandoc.List({pandoc.Str("Table\u{00A0}" .. number:match("^(%d+)%.") .. "."),
                       pandoc.RawInline("openxml", field(instr, number:match("%.(%d+)$")))})
  end
  inl:insert(pandoc.Space())
  inl:extend(title)
  local out = pandoc.List({styled("Caption", {pandoc.Para(inl)})})
  if #note > 0 then out:insert(styled(note_style, {pandoc.Para(note)})) end
  return out
end

-- tables: smaller type for wide ones ----------------------------------------------------------
local function cell_need(blocks)
  local m = 0
  pandoc.walk_block(pandoc.Div(blocks), {
    Str = function(s) m = math.max(m, utf8.len(s.text) or #s.text) end,
    Code = function(c)
      for w in c.text:gmatch("%S+") do m = math.max(m, math.ceil(1.5 * (utf8.len(w) or #w))) end
    end})
  return m
end

local function sized(t)
  local need = {}
  local function scan(rows)
    for _, row in ipairs(rows) do
      for i, cell in ipairs(row.cells) do need[i] = math.max(need[i] or 0, cell_need(cell.contents) + 2) end
    end
  end
  scan(t.head.rows)
  for _, body in ipairs(t.bodies) do scan(body.body) end
  local total = 0
  for _, n in pairs(need) do total = total + n end
  -- text width 15.24 cm holds about 85 characters of 10 pt Times New Roman
  local style = total > 110 and "Table Tiny" or (total > 80 and "Table Small" or nil)
  if not style then return t end
  local function wrap(rows)
    local out = pandoc.List()
    for _, row in ipairs(rows) do
      local cells = pandoc.List()
      for _, cell in ipairs(row.cells) do
        -- pandoc styles every cell paragraph "Compact"; a character style on the inlines is
        -- what it honours inside table cells
        cell.contents = pandoc.Blocks(cell.contents):walk({
          Code = function(c) return pandoc.Str(c.text) end}):walk({
          Plain = function(b) return pandoc.Plain({pandoc.Span(b.content, pandoc.Attr("", {}, {["custom-style"] = style}))}) end,
          Para = function(b) return pandoc.Para({pandoc.Span(b.content, pandoc.Attr("", {}, {["custom-style"] = style}))}) end})
        cells:insert(cell)
      end
      row.cells = cells
      out:insert(row)
    end
    return out
  end
  t.head.rows = wrap(t.head.rows)
  local bodies = pandoc.List()
  for _, body in ipairs(t.bodies) do body.body = wrap(body.body); bodies:insert(body) end
  t.bodies = bodies
  return t
end

-- biodata page ------------------------------------------------------------------------------
local function run(text, rpr)
  return "<w:r>" .. (rpr and ("<w:rPr>" .. rpr .. "</w:rPr>") or "") ..
    '<w:t xml:space="preserve">' .. esc(text) .. "</w:t></w:r>"
end
local BLANK = string.rep("_", 30)

local function biodata(attrs)
  for _, k in ipairs({"name", "reg", "email"}) do
    if not attrs[k] or attrs[k] == "" then
      io.stderr:write("thesis.lua: biodata needs name, reg and email\n"); os.exit(1)
    end
  end
  local function line(label, value)
    return '<w:p><w:pPr><w:pStyle w:val="BiodataLine"/></w:pPr>' .. run(label, "<w:b/>") ..
      "<w:r><w:tab/></w:r>" .. run(":\u{00A0}" .. value) .. "</w:p>"
  end
  local function cont(value)
    return '<w:p><w:pPr><w:pStyle w:val="BiodataLine"/></w:pPr><w:r><w:tab/></w:r>' .. run("  " .. value) .. "</w:p>"
  end
  local border = '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>' ..
    '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>' ..
    '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>' ..
    '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
  local none = '<w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/>'
  -- personal build: the photo replaces the word "Photo" later (biodata.insert_photos), so the cell needs
  -- no side margins and centres it; the address is one paragraph that wraps under its own text
  local has_photo = attrs["photo"] and attrs["photo"] ~= ""
  local photo_text = has_photo and ("[[photo:" .. attrs["photo"] .. "]]") or "Photo"
  local photo_cell = has_photo and '<w:tcMar><w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tcMar><w:vAlign w:val="center"/>' or ""
  local mobile = (attrs["mobile"] and attrs["mobile"] ~= "") and attrs["mobile"] or BLANK
  local address
  if attrs["address"] and attrs["address"] ~= "" then
    address = '<w:p><w:pPr><w:pStyle w:val="BiodataLine"/><w:ind w:left="2200" w:hanging="2080"/></w:pPr>' ..
      run("Permanent Address", "<w:b/>") .. "<w:r><w:tab/></w:r>" .. run(":\u{00A0}" .. attrs["address"]) .. "</w:p>"
  else
    address = line("Permanent Address", BLANK) .. cont(BLANK) .. cont(BLANK)
  end
  -- photo box 3.5 x 4.5 cm (a passport photo) in its own fixed-height cell; the details to its right
  local nogrid = '<w:tblBorders>' .. none .. '<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
  local photo = '<w:tbl><w:tblPr><w:tblW w:w="1984" w:type="dxa"/><w:tblLayout w:type="fixed"/>' .. nogrid ..
    '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="1" w:noVBand="1"/></w:tblPr>' ..
    '<w:tblGrid><w:gridCol w:w="1984"/></w:tblGrid><w:tr><w:trPr><w:trHeight w:val="2552" w:hRule="exact"/><w:cantSplit/></w:trPr>' ..
    '<w:tc><w:tcPr><w:tcW w:w="1984" w:type="dxa"/><w:tcBorders>' .. border .. '</w:tcBorders>' .. photo_cell .. '</w:tcPr>' ..
    '<w:p><w:pPr><w:pStyle w:val="BiodataPhoto"/></w:pPr>' .. run(photo_text) .. "</w:p></w:tc></w:tr></w:tbl><w:p/>"
  local xml = '<w:tbl><w:tblPr><w:tblW w:w="8640" w:type="dxa"/><w:tblLayout w:type="fixed"/>' .. nogrid ..
    '<w:tblCellMar><w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar>' ..
    '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="1" w:noVBand="1"/></w:tblPr>' ..
    '<w:tblGrid><w:gridCol w:w="1984"/><w:gridCol w:w="227"/><w:gridCol w:w="6429"/></w:tblGrid>' ..
    '<w:tr><w:trPr><w:cantSplit/></w:trPr>' ..
    '<w:tc><w:tcPr><w:tcW w:w="1984" w:type="dxa"/><w:tcBorders>' .. none .. '</w:tcBorders></w:tcPr>' .. photo .. "</w:tc>" ..
    '<w:tc><w:tcPr><w:tcW w:w="227" w:type="dxa"/><w:tcBorders>' .. none .. '</w:tcBorders></w:tcPr><w:p/></w:tc>' ..
    '<w:tc><w:tcPr><w:tcW w:w="6429" w:type="dxa"/><w:tcBorders>' .. none .. '</w:tcBorders></w:tcPr>' ..
    line("Name", attrs["name"]) .. line("Register No.", attrs["reg"]) ..
    line("Mobile Number", mobile) .. line("E-mail", attrs["email"]) .. address ..
    "</w:tc></w:tr></w:tbl>"
  return pandoc.RawBlock("openxml", xml)
end

-- the filter ----------------------------------------------------------------------------------
function Pandoc(doc)
  number_all(doc.blocks)
  local out_path = os.getenv("REPORT_NUMBERS_JSON")
  if out_path then
    local f = io.open(out_path, "w"); f:write(pandoc.json.encode(numbers)); f:close()
  end
  local logo = doc.meta.logo and stringify(doc.meta.logo) or nil

  local function fix_cites(el)
    for _, c in ipairs(el.citations) do if not is_xref(c.id) then return nil end end
    local res = pandoc.List()
    for i, c in ipairs(el.citations) do
      if i > 1 then res:insert(pandoc.Str(i == #el.citations and " and " or ", ")) end
      res:extend(ref_inlines(c.id, c.mode == "SuppressAuthor"))
    end
    return res
  end

  local biodata_seen = false

  -- the Front Heading style starts a new page (pageBreakBefore), as Heading 1 does
  local function front_heading(inlines, toc_text, toc)
    local content = pandoc.List(inlines)
    if toc then content:insert(tc(toc_text, 1)) end
    return pandoc.List({styled("Front Heading", {pandoc.Para(content)})})
  end

  local function header(h)
    local num = h.attributes["number"]
    h.attributes["number"] = nil
    local title = stringify(h.content)
    if h.level == 1 and not num then
      return front_heading(h.content, title, not h.classes:includes("notoc"))
    end
    if h.level == 1 then
      local c = pandoc.List({pandoc.RawInline("openxml", '<w:r><w:t xml:space="preserve">CHAPTER ' .. num ..
        '</w:t></w:r><w:r><w:br/></w:r>')})
      c:extend(h.content)
      c:insert(tc(num .. "\u{2003}" .. title, 1))
      h.content = c
      return h
    end
    if h.level >= 4 then
      return styled("Minor Heading", {pandoc.Para(h.content)})
    end
    if num then
      h.content:insert(1, pandoc.Str(num .. "\u{2003}"))
      h.content:insert(tc(num .. "\u{2003}" .. title, h.level))
    end
    return h
  end

  local function figure(f)
    local n = f.attributes["number"]
    local img
    pandoc.walk_block(f, {Image = function(i) img = i end})
    if not img then io.stderr:write("thesis.lua: figure without image\n"); os.exit(1) end
    img.caption = {}
    local short = f.attributes["short"] or img.attributes["short"]
    img.attributes["short"] = nil
    local title, note = title_and_note(short, f.caption.long)
    local out = pandoc.List({styled("Figure Image", {pandoc.Para({img})})})
    out:extend(caption_blocks("Figure", n, "SEQ Figure \\* ARABIC", title, note, "Caption Note"))
    return out
  end

  local function toc_field(instr, marker)
    return pandoc.RawBlock("openxml",
      '<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r>' ..
      '<w:r><w:instrText xml:space="preserve"> ' .. esc(instr) .. ' </w:instrText></w:r>' ..
      '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>' .. marker .. '</w:t></w:r>' ..
      '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
  end

  local function div(d)
    if d.identifier:match("^tbl:") then
      local n, seq = d.attributes["number"], d.attributes["seq"]
      local out = pandoc.List()
      for _, b in ipairs(d.content) do
        if b.t == "Table" then
          local title, note = title_and_note(d.attributes["short"], b.caption.long)
          b.caption = pandoc.Caption({})
          b.identifier = d.identifier
          local instr = "SEQ Table \\* ARABIC" .. (seq == "1" and " \\r 1" or "")
          out:extend(caption_blocks("Table", n, instr, title, note, "Table Note"))
          out:insert(sized(b))
        else
          out:insert(b)
        end
      end
      return out
    end
    if d.classes:includes("lists") then
      local out = pandoc.List()
      out:extend(front_heading({pandoc.Str("Table of Contents")}, "", false))
      out:insert(toc_field('TOC \\f \\l "1-3" \\h \\z', "@@TOC@@"))
      out:extend(front_heading({pandoc.Str("List of Tables")}, "List of Tables", true))
      out:insert(toc_field('TOC \\h \\z \\c "Table"', "@@LOT@@"))
      out:extend(front_heading({pandoc.Str("List of Figures")}, "List of Figures", true))
      out:insert(toc_field('TOC \\h \\z \\c "Figure"', "@@LOF@@"))
      return out
    end
    if d.classes:includes("frontmatter-end") then
      -- footer ids are added by the build (rIdTSFooter, rIdTSFooterFirst)
      return pandoc.RawBlock("openxml", '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:sectPr>' ..
        '<w:footerReference w:type="default" r:id="rIdTSFooter"/>' ..
        '<w:footerReference w:type="first" r:id="rIdTSFooterFirst"/>' ..
        '<w:pgSz w:w="12240" w:h="15840"/>' ..
        '<w:pgMar w:top="1440" w:right="1800" w:bottom="851" w:left="1800" w:header="720" w:footer="720" w:gutter="0"/>' ..
        '<w:pgNumType w:fmt="lowerRoman" w:start="1"/><w:titlePg/></w:sectPr></w:pPr></w:p>')
    end
    if d.classes:includes("thesis-logo") then
      if not logo then io.stderr:write("thesis.lua: metadata 'logo' (the college logo) is missing\n"); os.exit(1) end
      return styled("TP Logo", {pandoc.Para({pandoc.Image({}, logo, "", pandoc.Attr("", {}, {width = "6.93cm"}))})})
    end
    if d.classes:includes("biodata") then
      local out = front_heading({pandoc.Str("Biodata")}, "Biodata", not biodata_seen)
      biodata_seen = true
      out:insert(biodata(d.attributes))
      return out
    end
    if d.classes:includes("note-page") then
      return styled("Note Text", d.content)      -- the style starts a new page
    end
    return nil
  end

  local function span(s)
    if s.classes:includes("tab") then return pandoc.RawInline("openxml", "<w:r><w:tab/></w:r>") end
    return nil
  end

  local function raw(r)
    if (r.format == "tex" or r.format == "latex") and r.text:match("^%s*\\newpage%s*$") then
      return PAGE_BREAK
    end
    return nil
  end

  doc = doc:walk({Cite = fix_cites, Span = span})
  doc = doc:walk({Header = header, Figure = figure, Div = div, RawBlock = raw})
  return doc
end
