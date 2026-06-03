Room for Thought — Make a Plan First//
First let’s create an outline for the pull request description. Do not generate a title and description, only write the outline. Be sure to think about what the categories of the change are (i.e. 1. A change to add the--foo argument, 2. Add retries for network calls, etc) based on what you see in the diff.


A good pull request description is clear, concise, and fully lays out the complex parts of the change. When composing a pull request description, the best ones cite the changes with the description, but also don't over describe small changes (especially one line changes).

Given this, create an outline for the pull request description, only writing the outline

… etc …

Self Correction — Critique yourself//
Now we will generate the title for the PR. The title should succinctly indicate what the pull request aims to do. Ideally, it should be a short and clear description of the purpose of the pull request.

Generate 5 possible radically different titles and then critique them.

Finally generate a refined final title after the critique.


Puppetry — Speaking for the model//
For instance, when we want the model to output a JSON object for the pull request script, we do this:

User: Finally output the title and description according to the
below JSON format, it is very important to follow the format below exactly.

{
"title": "",<br>"description": "<description">,<br>}</code></p></body></html>

Assistant: {
"title": "