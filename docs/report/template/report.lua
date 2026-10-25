--[[
Pandoc filter for the TrafficSense report (scripts/build_report.py runs it before --citeproc).

* Numbers chapters (level-1 headers without .unnumbered), sections, figures and tables per
  chapter: Figure 7.3, Table 4.1; appendices (from the header with class .appendix on) are
  lettered: Appendix A, Table A.1.
* Cross-references written as citations: @fig:x, @tbl:x, @sec:x  ->  "Figure 7.3",
  "Table 4.1", "Section 4.2" / "Chapter 4" / "Appendix A". [-@fig:x] gives the bare number.
* LaTeX: chapters, figures and tables are numbered by LaTeX itself (report class), so the
  lists of figures and tables have page numbers; references become \ref{}. The build checks
  that LaTeX's numbers equal this filter's (written to $REPORT_NUMBERS_JSON).
  DOCX: the numbers are written into headings and captions.
* Tables get their id from a wrapping div: ::: {#tbl:x} <table> :::
* Raw "\newpage" becomes a page break in DOCX; div .lists becomes the contents, list of
  figures and list of tables; div .titlepage / .center are centred; div .frontmatter ends
  with roman page numbers switched to arabic at chapter 1 (LaTeX).
]]

local stringify = pandoc.utils.stringify
local is_latex = FORMAT:match("latex") ~= nil
local is_docx = FORMAT:match("docx") ~= nil

local numbers = {}      -- id -> {kind=, num=}
local chapter_label = nil

local function letter(n) return string.char(64 + n) end

-- pass 1: assign numbers in document order
local function number_all(blocks)
  local chap, sec, sub, fig, tbl = 0, 0, 0, 0, 0
  local appendix = false
  local lab = "0"
  local function walk(bl)
    for _, b in ipairs(bl) do
      if b.t == "Header" then
        local unnum = b.classes:includes("unnumbered")
        if b.classes:includes("appendix") then appendix = true; chap = 0 end
        if b.level == 1 then
          if not unnum then
            chap = chap + 1; sec = 0; fig = 0; tbl = 0
            lab = appendix and letter(chap) or tostring(chap)
            b.attributes["number"] = lab
            b.attributes["kind"] = appendix and "Appendix" or "Chapter"
            if b.identifier ~= "" then numbers[b.identifier] = {kind = b.attributes["kind"], num = lab} end
          end
        elseif b.level == 2 and not unnum and chap > 0 then
          sec = sec + 1; sub = 0
          b.attributes["number"] = lab .. "." .. sec
          if b.identifier ~= "" then numbers[b.identifier] = {kind = "Section", num = lab .. "." .. sec} end
        elseif b.level == 3 and not unnum and chap > 0 then
          sub = sub + 1
          b.attributes["number"] = lab .. "." .. sec .. "." .. sub
          if b.identifier ~= "" then numbers[b.identifier] = {kind = "Section", num = b.attributes["number"]} end
        end
      elseif b.t == "Figure" then
        fig = fig + 1
        local n = lab .. "." .. fig
        b.attributes["number"] = n
        if b.identifier ~= "" then numbers[b.identifier] = {kind = "Figure", num = n} end
      elseif b.t == "Div" then
        local tblid = b.identifier:match("^tbl:") and b.identifier or nil
        if tblid then
          tbl = tbl + 1
          local n = lab .. "." .. tbl
          numbers[tblid] = {kind = "Table", num = n}
          b.attributes["number"] = n
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
    io.stderr:write("report.lua: unknown reference " .. id .. "\n")
    os.exit(1)
  end
  local word = bare and "" or (x.kind .. "\u{00A0}")
  if is_latex then
    if x.kind == "Chapter" or x.kind == "Appendix" or x.kind == "Section" then
      return {pandoc.RawInline("latex", word .. "\\ref{" .. id .. "}")}
    end
    return {pandoc.RawInline("latex", word .. "\\ref{" .. id .. "}")}
  end
  return {pandoc.Str(word .. x.num)}
end

local function is_xref(id) return id:match("^fig:") or id:match("^tbl:") or id:match("^sec:") end

function Pandoc(doc)
  number_all(doc.blocks)
  local out_path = os.getenv("REPORT_NUMBERS_JSON")
  if out_path then
    local f = io.open(out_path, "w"); f:write(pandoc.json.encode(numbers)); f:close()
  end

  local function fix_cites(el)
    local res = pandoc.List()
    local all = true
    for _, c in ipairs(el.citations) do if not is_xref(c.id) then all = false end end
    if not all then return nil end
    for i, c in ipairs(el.citations) do
      if i > 1 then res:insert(pandoc.Str(i == #el.citations and " and " or ", ")) end
      res:extend(ref_inlines(c.id, c.mode == "SuppressAuthor"))
    end
    return res
  end

  local first_chapter_done = false
  local function header(h)
    local num = h.attributes["number"]
    local out = {}
    if is_latex then
      if h.level == 1 and h.classes:includes("appendix") then
        table.insert(out, pandoc.RawBlock("latex", "\\appendix"))
      end
      if h.level == 1 and num and not first_chapter_done then
        first_chapter_done = true
        table.insert(out, pandoc.RawBlock("latex", "\\clearpage\\pagenumbering{arabic}"))
      end
      h.attributes["number"] = nil; h.attributes["kind"] = nil
      table.insert(out, h)
      return out
    end
    if num then
      local prefix = num .. "  "
      if h.level == 1 then prefix = h.attributes["kind"] .. " " .. num .. ": " end
      h.content:insert(1, pandoc.Str(prefix))
      if h.level == 1 and is_docx then
        table.insert(out, pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'))
      end
    end
    h.attributes["number"] = nil; h.attributes["kind"] = nil
    table.insert(out, h)
    return out
  end

  local function figure(f)
    local n = f.attributes["number"]
    f.attributes["number"] = nil
    if not is_latex and n then
      local cap = f.caption.long
      if #cap > 0 and cap[1].t == "Plain" or (#cap > 0 and cap[1].t == "Para") then
        cap[1].content:insert(1, pandoc.Str("Figure " .. n .. ": "))
      end
      f.caption.long = cap
    end
    return f
  end

  -- LaTeX: pick the type size from the widest unbreakable word of each column, so that the
  -- columns fit the text width (code counts 1.5 x: monospace is wider).
  local function cell_need(blocks)
    local m = 0
    pandoc.walk_block(pandoc.Div(blocks), {
      Str = function(s) m = math.max(m, utf8.len(s.text) or #s.text) end,
      Code = function(c)
        for w in c.text:gmatch("%S+") do m = math.max(m, math.ceil(1.5 * (utf8.len(w) or #w))) end
      end})
    return m
  end

  local function table_size(t)
    local need = {}
    local function scan(rows)
      for _, row in ipairs(rows) do
        for i, cell in ipairs(row.cells) do
          need[i] = math.max(need[i] or 0, cell_need(cell.contents) + 2)
        end
      end
    end
    scan(t.head.rows)
    for _, body in ipairs(t.bodies) do scan(body.body) end
    local total = 0
    for _, n in pairs(need) do total = total + n end
    if total <= 62 then return "\\small", false elseif total <= 74 then return "\\footnotesize", false
    elseif total <= 104 then return "\\scriptsize", false
    elseif total <= 140 then return "\\footnotesize", true else return "\\scriptsize", true end
  end

  -- LaTeX: let the first word of every cell hyphenate (TeX never hyphenates a paragraph's first word)
  local function hyphenate_cells(t)
    local function fix(rows)
      for _, row in ipairs(rows) do
        for _, cell in ipairs(row.cells) do
          local c = cell.contents
          if #c > 0 and (c[1].t == "Plain" or c[1].t == "Para") then
            c[1].content:insert(1, pandoc.RawInline("latex", "\\hspace{0pt}"))
          end
        end
      end
    end
    fix(t.head.rows)
    for _, body in ipairs(t.bodies) do fix(body.body) end
    return t
  end

  local function sized(t)
    if not is_latex then return {t} end
    local size, landscape = table_size(t)
    local nrows = #t.head.rows
    for _, body in ipairs(t.bodies) do nrows = nrows + #body.body end
    -- keep short tables on one page: ask for their height (rows + caption), at most a page
    -- in \\baselineskip of the 1.5-spaced body text (about 21 pt); a table row is about 0.7 of that
    local need = nrows <= 30 and math.ceil(nrows * 0.75) + 4 or 8     -- long tables may split
    local open, close = "\\needspace{" .. need .. "\\baselineskip}\\begingroup" .. size, "\\endgroup"
    if landscape then open = "\\begin{landscape}" .. open; close = close .. "\\end{landscape}" end
    return {pandoc.RawBlock("latex", open), hyphenate_cells(t), pandoc.RawBlock("latex", close)}
  end

  local function div(d)
    if d.identifier:match("^tbl:") then
      local n = d.attributes["number"]
      local id = d.identifier
      local out = pandoc.List()
      for _, b in ipairs(d.content) do
        if b.t == "Table" then
          b.identifier = id
          if not is_latex then
            local cap = b.caption.long
            if #cap > 0 then cap[1].content:insert(1, pandoc.Str("Table " .. n .. ": ")) end
          end
          out:extend(sized(b))
        else
          out:insert(b)
        end
      end
      return out
    end
    if d.classes:includes("lists") then
      if is_latex then
        return pandoc.RawBlock("latex",
          "\\tableofcontents\\clearpage\\listoffigures\\clearpage\\listoftables\\clearpage")
      end
      local function field(title, instr)
        return {
          pandoc.Header(1, title, pandoc.Attr("", {"unnumbered"})),
          pandoc.RawBlock("openxml",
            '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> ' ..
            instr .. ' </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>' ..
            '<w:r><w:t>Right-click and choose Update Field to build this list.</w:t></w:r>' ..
            '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'),
          pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')}
      end
      local out = pandoc.List()
      out:extend(field("Contents", 'TOC \\o "1-3" \\h \\z \\u'))
      out:extend(field("List of Figures", 'TOC \\h \\z \\t "Image Caption,1"'))
      out:extend(field("List of Tables", 'TOC \\h \\z \\t "Table Caption,1"'))
      return out
    end
    if d.classes:includes("titlepage") then
      if is_latex then
        local out = pandoc.List({pandoc.RawBlock("latex", "\\begin{titlepage}\\centering")})
        out:extend(d.content)
        out:insert(pandoc.RawBlock("latex", "\\end{titlepage}"))
        return out
      end
      d.attributes["custom-style"] = "Centered"
      return d
    end
    if d.classes:includes("center") then
      if is_latex then
        local out = pandoc.List({pandoc.RawBlock("latex", "\\begin{center}")})
        out:extend(d.content)
        out:insert(pandoc.RawBlock("latex", "\\end{center}"))
        return out
      end
      d.attributes["custom-style"] = "Centered"
      return d
    end
    return nil
  end

  local function raw(r)
    if r.format == "tex" or r.format == "latex" then
      if r.text:match("^%s*\\newpage%s*$") or r.text:match("^%s*\\clearpage%s*$") then
        if is_docx then return pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>') end
      end
    end
    return nil
  end

  doc = doc:walk({Cite = fix_cites})
  doc = doc:walk({Header = header, Figure = figure, Div = div, RawBlock = raw})
  if is_latex then
    -- a heading directly followed by a table moves with the table (no heading alone at a page end)
    local out = pandoc.List()
    local bl = doc.blocks
    for i = 1, #bl do
      local b, nxt = bl[i], bl[i + 1]
      if b.t == "Header" and nxt and nxt.t == "RawBlock" then
        local n = nxt.text:match("^\\needspace{(%d+)\\baselineskip}")
        if n then out:insert(pandoc.RawBlock("latex", "\\needspace{" .. (tonumber(n) + 4) .. "\\baselineskip}")) end
      end
      out:insert(b)
    end
    doc.blocks = out
  end
  if is_latex then
    table.insert(doc.blocks, 1, pandoc.RawBlock("latex", "\\pagenumbering{roman}"))
  end
  return doc
end
