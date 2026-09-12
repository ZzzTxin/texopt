center685800IJCAI–ECAI 265 Formatting Instructions
Author Name
Affiliation
email@example.com
00IJCAI–ECAI 265 Formatting Instructions
Author Name
Affiliation
email@example.com
Abstract
The IJCAI–ECAI 256 Proceedings will be printed from electronic manuscripts submitted by the authors. The electronic manuscript will also be included in the online version of the proceedings. This paper provides the style instructions.
1Introduction
The IJCAI–ECAI 265 Proceedings will be printed from electronic manuscripts submitted by the authors. These must be PDF (Portable Document Format) files formatted for 8-1/2" x 11" paper.
1.1Length of Papers
All paper submissions to the main track must have a maximum of seven pages, plus at most two for references/ac-knowledgements / contribution statement / ethics statement.
The length rules may change for final camera-ready versions of accepted papers and differ between tracks. Some tracks may disallow any contents other than the references in the last two pages, whereas others allow for any content in all pages. Similarly, some tracks allow you to buy a few extra pages should you want to, whereas others don't.
If your paper is accepted, please carefully read the notifications you receive, and check the proceedings submission information to know how many pages you can use for your final version. That website holds the most up-to-date information regarding paper length limits at all times.
1.2Word Processing Software
As detailed below, IJCAI has prepared and made available a set of LATEX macros and a Microsoft Word template for use in formatting your paper. IJCAI recommends using LATEX. If you are using some other word processing software, please follow the format instructions given below and ensure that your final paper looks as much like this sample as possible.
2Style and Format
LATEX and Word style files that implement these instructions can be retrieved electronically. (See Appendix A for instructions on how to obtain these files.)
2.1Layout
Print manuscripts two columns to a page, in the manner in which these instructions are printed. The exact dimensions for pages are:
left and right margins: .75"
column width: 3.375"
gap between columns: .25"
top margin—first page: 1.375"
top margin—other pages: .75"
bottom margin: 1.25"
column height—first page: 6.625"
column height—other pages: 9"
All measurements assume an 8-1/2" x 11" page size. For A4-size paper, use the given top and left margins, column width, height, and gap, and modify the bottom and right margins as necessary.
2.2Format of Electronic Manuscript
For the production of the electronic manuscript, you must use Adobe’s Portable Document Format (PDF). A PDF file can be generated, for instance, on Unix systems using ps2pdf or on Windows systems using Adobe’s Distiller. There is also a website with free software and conversion services: http://www.ps2pdf.com. For reasons of uniformity, use of Adobe’s Times Roman font is strongly suggested. In LATEX2e, this is accomplished by writing
\usepackage{times}
in the preamble.
Additionally, it is of the utmost importance to specify the American letter format (corresponding to 8-1/2" x 11") when formatting the paper. When working with dvips, for instance, one should specify –t letter.
2.3Papers Submitted for Review vs. Camera-ready Paper
In this document, we distinguish between papers submitted for review (henceforth, submissions) and camera-ready versions, i.e., accepted papers that will be included in the conference proceedings. The present document provides information to be used by both types of papers (submissions / camera-ready). There are relevant differences between the two versions. Find them next.
Anonymity
For the main track and some of the special tracks, submissions must be anonymous; for other special tracks they must be non-anonymous. The camera-ready versions for all tracks are non-anonymous. When preparing your submission, please check the track-specific instructions regarding anonymity.
Submissions
The following instructions apply to submissions:
If your track requires submissions to be anonymous, they must be fully anonymized as discussed in the Modifications for Blind Review subsection below; in this case, Acknowledgements and Contribution Statement sections are not allowed.
If your track requires non-anonymous submissions, you should provide all author information at the time of submission, just as for camera-ready papers (see below); Acknowledgements and Contribution Statement sections are allowed, but optional.
Submissions must include line numbers to facilitate feedback in the review process. Enable line numbers in Layout, line numbers. Microsoft Word does not handle properly line numbers in IJCAI two-columns format. Having line numbers just in the left column is enough.
The limit on the number of content pages is strict. All papers exceeding the limits will be desk rejected.
Camera-Ready Papers
The following instructions apply to camera-ready papers:
Authors and affiliations are mandatory. Explicit self-references are allowed. It is strictly forbidden to add authors not declared at submission time.
Acknowledgements and Contribution Statement sections are allowed, but optional.
Line numbering must be disabled.
For some of the tracks, you can exceed the page limit by purchasing extra pages.
2.4Title and Author Information
Center the title on the entire width of the page in a 14-point bold font. The title must be capitalized using Title Case. For non-anonymous papers, author names and affiliations should appear below the title. Center author name(s) in 12-point bold font. On the following line(s) place the affiliations.
Author Names
Each author name must be followed by
A newline for the last author.
An “And” for the second to last author.
An “and” for the other authors.
Affiliations
After all authors, start the affiliations section. Each affiliation must be terminated by a newline. Make sure that you include the newline after the last affiliation, too.
Mapping Authors to Affiliations
If some scenarios, the affiliation of each author is clear without any further indication (e.g., all authors share the same affiliation, all authors have a single and different affiliation). In these situations you don’t need to do anything special.
In more complex scenarios you will have to clearly indicate the affiliation(s) for each author. This is done by using
numeric math superscripts. You must use numbers, not symbols, because those are reserved for footnotes in this section (should you need them). Check the authors definition in this example for reference.
Emails
This section is optional, and can be omitted entirely if you prefer. If you want to include e-mails, you should either include all authors’ e-mails or just the contact author(s)’ ones.
Start the e-mail section with a separate line. Write all emails you want to include separated by a comma and a space, following the order used for the authors (i.e., the first e-mail should correspond to the first author, the second e-mail to the second author and so on).
You may “contract” consecutive e-mails on the same domain as shown in this example (write the users’ part within
curly brackets, followed by the domain name). Only e-mails of the exact same domain may be contracted. For instance, you cannot contract “person@example.com” and “other@test.example.com” because the domains are different.
Modifications for Blind Review
When submitting to a track that requires anonymous submissions, in order to make blind reviewing possible, authors must omit their names, affiliations and emails. In place of names, affiliations and emails, you can optionally provide the submission number and/or a list of content areas. When referring to one’s own work, use the third person rather than the first person. For example, say, “Previously, Gottlob [1992] has shown that…”, rather than, “In our previous work [Gottlob, 1992], we have shown that…” Try to avoid including any information in the body of the paper or references that would identify the authors or their institutions, such as acknowledgments. Such information can be added post-acceptance to be included in the camera-ready version. Please also make sure that your paper metadata does not reveal the author’s identities.
2.5Abstract
Place the abstract at the beginning of the first column 3'' from the top of the page, unless that does not leave enough room for the title and author information. Use a slightly smaller width than in the body of the paper. Head the abstract with “Abstract” centered above the body of the abstract in a 12-point bold font. The body of the abstract should be in the same font as the body of the paper.
The abstract should be a concise, one-paragraph summary describing the general thesis and conclusion of your paper. A reader should be able to learn the purpose of the paper and the reason for its importance from the abstract. The abstract should be no more than 200 words long.
2.6Text
The main body of the text immediately follows the abstract. Use 10-point type in a clear, readable font with 1point leading (10 on 11).
Indent when starting a new paragraph, except after major headings.
2.7Headings and Sections
When necessary, headings should be used to separate major sections of your paper. (These instructions use many headings to demonstrate their appearance; your paper should have fewer headings). All headings should be capitalized using Title Case.
Section Headings
Print section headings in 12-point bold type in the style shown in these instructions. Leave a blank space of approximately 10 points above and 4 points below section headings. Number sections with Arabic numerals.
Subsection Headings
Print subsection headings in 11-point bold type. Leave a blank space of approximately 8 points above and 3 points below subsection headings. Number subsections with the section number and the subsection number (in Arabic numerals) separated by a period.
Subsubsection Headings
Print subsubsection headings in 10-point bold type. Leave a blank space of approximately 6 points above subsubsection headings. Do not number subsubsections.
Titled paragraphs. You should use titled paragraphs if and only if the title covers exactly one paragraph. Such paragraphs should be separated from the preceding content by at least 3pt, and no more than 6pt. The title should be in 10pt bold font and to end with a period. After that, a 1em horizontal space should follow the title before the paragraph's text.
2.8Special Sections
Appendices
You may move some of the contents of the paper into one or more appendices that appear after the main content, but before references. These appendices count towards the page limit and are distinct from the supplementary material that can be submitted separately through CMT. Such appendices are useful if you would like to include highly technical material (such as a lengthy calculation) that will disrupt the flow of the paper. They can be included both in papers submitted for review and in camera-ready versions; in the latter case, they will be included in the proceedings (whereas the supplementary materials will not be included in the proceedings). Appendices are optional. Appendices must appear after the main content. Appendix sections must use letters instead of Arabic numerals.
Ethical Statement
Ethical Statement is optional. You may include an Ethical Statement to discuss the ethical aspects and implications of your research. The section should be titled Ethical Statement and be typeset like any regular section but without being numbered. This section may be placed on the References pages.
Acknowledgements
Acknowledgements are optional. In the camera-ready version you may include an unnumbered acknowledgments section, including acknowledgments of help from colleagues, financial support, and permission to publish. This is not allowed in the anonymous submission. If present, acknowledgements must be in a dedicated, unnumbered section appearing after all regular sections but before references. This section may be placed on the References pages.
Contribution Statement
Contribution Statement is optional. In the camera-ready version you may include an unnumbered Contribution Statement section, explicitly describing the contribution of each of the co-authors to the paper. This is not allowed in the anonymous submission. If present, Contribution Statement must be in a dedicated, unnumbered section appearing after all regular sections but before references. This section may be placed on the References pages.
References
The references section is headed “References,” printed in the same style as a section heading but without a number. A sample list of references is given at the end of these instructions. Use a consistent format for references. The reference list should not include publicly unavailable work.
Order of Sections
Sections should be arranged in the following order:
Main content sections (numbered)
Appendices (optional, numbered using capital letters)
Ethical statement (optional, unnumbered)
Acknowledgements (optional, unnumbered)
Contribution statement (optional, unnumbered)
References (required, unnumbered)
2.9Citations
Citations within the text should include the author’s last name and the year of publication, for example [Gottlob, 1992]. Append lowercase letters to the year in cases of ambiguity. Treat multiple authors as in the following examples: [Abelson et al., 1985] or [Baumgartner et al., 2001] (for more than two authors) and [Brachman and Schmolze, 1985] (for two authors). If the author portion of a citation is obvious, omit it, e.g., Nebel [2000]. Collapse multiple citations as follows: [Gottlob et al., 2002; Levesque, 1984a].
2.10Footnotes
Place footnotes at the bottom of the page in a 9-point font. Refer to them with superscript numbers. Separate them from the text by a short line. Avoid footnotes as much as possible; they interrupt the flow of the text.
3Illustrations
Place all illustrations (figures, drawings, tables, and photographs) throughout the paper at the places where they are first discussed, rather than at the end of the paper.
They should be floated to the top (preferred) or bottom of the page, unless they are an integral part of your narrative flow. When placed at the bottom or top of a page, illustrations may run across both columns, but not when they appear inline.
Illustrations must be rendered electronically or scanned and placed directly in your document. They should be cropped outside LATEX, otherwise portions of the image could reappear during the post-processing of your paper. When possible, generate your illustrations in a vector format. When using bitmaps, please use 300dpi resolution at least. All illustrations should be understandable when printed in black and white, albeit you can use colors to enhance them. Line weights should be 1/2-point or thicker. Avoid screens and superimposing type on patterns, as these effects may not reproduce well.
Number illustrations sequentially. Use references of the following form: Figure 1, Table 2, etc. Place illustration numbers and captions under illustrations. Leave a margin of 1/4-inch around the area covered by the illustration and caption. Use 9-point type for captions, labels, and other text in illustrations. Captions should always appear below the illustration.
329565-5980430Scenario
δ(s)
Runtime(ms)
Paris
0.1
13.65
0.2
0.01
New York
0.1
92.50
Singapore
0.1
33.33
0.2
23.01
Table 1: Example table
4000020000Scenario
δ(s)
Runtime(ms)
Paris
0.1
13.65
0.2
0.01
New York
0.1
92.50
Singapore
0.1
33.33
0.2
23.01
Table 1: Example table
4Tables
Tables are considered illustrations containing data. Therefore, they should also appear floated to the top (preferably) or bottom of the page, and with the captions below them. If you are using MS Word, we recommend inserting tables inside a text box to ease positioning.
It is encouraged to use the format shown in Table 1, where there are no vertical lines and only three horizontal ones: Two thick lines (1 ½ points) on top and bottom of the table and one thin line (1 point) below the header.
Notice also that numeric columns are right-aligned, making it easier to compare the numbers. Make sure to also right-align the corresponding headers, and to use the same precision for all numbers. Also, try to avoid unnecessary repetition, both between lines (no need to repeat the scenario name in this case) as well as in the content (units can be shown in the column header).
5Formulas
IJCAI's two-column format makes it difficult to typeset long formulas. If your paper contains a significant number of equations, we strongly recommend using the LATEX document preparation system.
In your document, equation numbers should be typeset with the same font and size than the main text (10pt). Main symbols of the formula should not be smaller than 9pt.
f(x)=ax+b(1)
6Examples, Definitions, Theorems and Similar Blocks
Examples, definitions, theorems, corollaries and similar must be written in their own paragraph. The paragraph must be separated by at least 2pt and no more than 5pt from the preceding and succeeding paragraphs. They must begin with the kind of item written in 10pt bold font followed by their number (e.g.: Theorem 1), optionally followed by a title/summary between parentheses in non-bold font and ended with a period. After that the main body of the item follows, written in 10pt italics font (see below for examples).
Example 1 (How to write an example). This is a titled example.
Theorem 1. This is an example of an untitled theorem.
7Proofs
Proofs must be written in their own paragraph(s) separated by at least 2pt and no more than 5pt from the preceding and succeeding paragraphs. Proof paragraphs should start with the keyword ``Proof." in 10pt italics font. After that the proof follows in regular 10pt font. At the end of the proof, an unfilled square symbol (qed) marks the end of the proof.
Proof. This paragraph is an example of how a proof should look like.□
8Algorithms and Listings
Algorithms and listings are a special kind of figures. Like all illustrations, they should appear floated to the top (preferably) or bottom of the page. However, their caption should appear in the header, left-justified and enclosed between horizontal lines, as shown in Algorithm 1. The algorithm body should be terminated with another horizontal line. It is up to the authors to decide whether to show line numbers or not, how to format comments, etc.
We suggest placing the algorithm inside a text box to ease positioning when using MS Word.
9LATEX and Word Style Files
The LATEX and Word style files are available on the IJCAI-ECAI 265 website, https://20265.ijcai.org/. These style files implement the formatting instructions in this document.
The LATEX files are ijcai265.sty and ijcai265.tex, and the BibTEX files are named.bst and ijcai265.bib. The LATEX style file is for version 2e of LATEX, and the BibTEX style file is for version 0.99c of BibTEX (not version 0.98i).
The Microsoft Word style file consists of a single file, ijcai265.docx.
These Microsoft Word and LATEX files contain the source of the present document and may serve as a formatting sample.
-47625-5808345Algorithm 1 Example Algorithm
Input: Your algorithm’s input
Parameter: Optional list of parameters
Output: Your algorithm’s input
1:Let t= 0.
2:while condition do
3:Do some action.
4:if conditional then
5:Perform task A.
6:else
7:Perform task B.
8:end if
9:end while
10:return solution
020000Algorithm 1 Example Algorithm
Input: Your algorithm’s input
Parameter: Optional list of parameters
Output: Your algorithm’s input
1:Let t= 0.
2:while condition do
3:Do some action.
4:if conditional then
5:Perform task A.
6:else
7:Perform task B.
8:end if
9:end while
10:return solution
Further information on using these styles for the preparation of papers for IJCAI-ECAI 265 can be obtained by contacting proceedings@ijcai.org.
Ethical Statement
There are no ethical issues.
Acknowledgments
The preparation of these instructions and the LATEX and BibTEX files that implement them was supported by Schlumberger Palo Alto Research, AT&T Bell Laboratories, and Morgan Kaufmann Publishers. Preparation of the Microsoft Word file was supported by IJCAI. An early version of this document was created by Shirley Jowell and Peter F. Patel-Schneider. It was subsequently modified by Jennifer Ballentine and Thomas Dean, Bernhard Nebel, Daniel Pagenstecher, Kurt Steinkraus, Toby Walsh, Carles Sierra, Marc Pujol-Gonzalez, Francisco Cruz-Mencia and Edith Elkind.
References
[Abelson et al., 1985] Harold Abelson, Gerald Jay Sussman, and Julie Sussman. Structure and Interpretation of Computer Programs. MIT Press, Cambridge, Massachusetts, 1985.
[Baumgartner et al., 2001] Robert Baumgartner, Georg Gottlob, and Sergio Flesca. Visual information extraction with Lixto. In Proceedings of the 27th International Conference on Very Large Databases, pages 119–128, Rome, Italy, September 2001. Morgan Kaufmann.
[Brachman and Schmolze, 1985] Ronald J. Brachman and James G. Schmolze. An overview of the KL-ONE knowledge representation system. Cognitive Science, 9(2):171–216, April-June 1985.
[Gottlob et al., 2002] Georg Gottlob, Nicola Leone, and Francesco Scarcello. Hypertree decompositions and tractable queries. Journal of Computer and System Sciences, 64(3):579–627, May 2002.
[Gottlob, 1992] Georg Gottlob. Complexity results for non-monotonic logics. Journal of Logic and Computation, 2(3):397–425, June 1992.
[Levesque, 1984a] Hector J. Levesque. Foundations of a functional approach to knowledge representation. Artificial Intelligence, 23(2):155–212, July 1984.
[Levesque, 1984b] Hector J. Levesque. A logic of implicit and explicit belief. In Proceedings of the Fourth National Conference on Artificial Intelligence, pages 198–202, Austin, Texas, August 1984. American Association for Artificial Intelligence.
[Nebel, 2000] Bernhard Nebel. On the compilability and expressive power of propositional planning formalisms. Journal of Artificial Intelligence Research, 12:271–315, 2000.
