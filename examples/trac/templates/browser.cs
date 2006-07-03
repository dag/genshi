<?cs include "header.cs"?>
<?cs include "macros.cs"?>

<div id="ctxtnav" class="nav">
 <ul>
  <li class="first"><a href="<?cs var:browser.restr_changeset_href ?>">
   Last Change</a></li>
  <li class="last"><a href="<?cs var:browser.log_href ?>">
   Revision Log</a></li>
 </ul>
</div>


<div id="searchable">
<div id="content" class="browser">
 <h1><?cs call:browser_path_links(browser.path, browser) ?></h1>

 <div id="jumprev">
  <form action="" method="get">
   <div>
    <label for="rev">View revision:</label>
    <input type="text" id="rev" name="rev" value="<?cs
       var:browser.revision ?>" size="4" />
   </div>
  </form>
 </div>

 <?cs def:sortable_th(order, desc, class, title, href) ?>
 <th class="<?cs var:class ?><?cs if:order == class ?> <?cs
   if:desc ?>desc<?cs else ?>asc<?cs /if ?><?cs /if ?>">
  <a title="Sort by <?cs var:class ?><?cs
    if:order == class && !desc ?> (descending)<?cs /if ?>" 
     href="<?cs var:href[class] ?>"><?cs var:title ?></a>
 </th>
 <?cs /def ?>

 <?cs if:browser.is_dir ?>
  <table class="listing" id="dirlist">
   <thead>
    <tr><?cs 
     call:sortable_th(browser.order, browser.desc, 'name', 'Name', browser.order_href) ?><?cs 
     call:sortable_th(browser.order, browser.desc, 'size', 'Size', browser.order_href) ?>
     <th class="rev">Rev</th><?cs 
     call:sortable_th(browser.order, browser.desc, 'date', 'Age', browser.order_href) ?>
     <th class="change">Last Change</th>
    </tr>
   </thead>
   <tbody>
    <?cs if:len(chrome.links.up) ?>
     <tr class="even">
      <td class="name" colspan="5">
       <a class="parent" title="Parent Directory" href="<?cs
         var:chrome.links.up.0.href ?>">../</a>
      </td>
     </tr>
    <?cs /if ?>
    <?cs each:item = browser.items ?>
     <?cs set:change = browser.changes[item.rev] ?>
     <tr class="<?cs if:name(item) % #2 ?>even<?cs else ?>odd<?cs /if ?>">
      <td class="name"><?cs
       if:item.is_dir ?><?cs
        if:item.permission ?>
         <a class="dir" title="Browse Directory" href="<?cs
           var:item.browser_href ?>"><?cs var:item.name ?></a><?cs
        else ?>
         <span class="dir" title="Access Denied" href=""><?cs
           var:item.name ?></span><?cs
        /if ?><?cs
       else ?><?cs
        if:item.permission != '' ?>
         <a class="file" title="View File" href="<?cs
           var:item.browser_href ?>"><?cs var:item.name ?></a><?cs
        else ?>
         <span class="file" title="Access Denied" href=""><?cs
           var:item.name ?></span><?cs
        /if ?><?cs
       /if ?>
      </td>
      <td class="size"><?cs var:item.size ?></td>
      <td class="rev"><?cs if:item.permission != '' ?><a title="View Revision Log" href="<?cs
        var:item.log_href ?>"><?cs var:item.rev ?></a><?cs else ?><?cs var:item.rev ?><?cs /if ?></td>
      <td class="age"><span title="<?cs var:browser.changes[item.rev].date ?>"><?cs
        var:browser.changes[item.rev].age ?></span></td>
      <td class="change">
       <span class="author"><?cs var:browser.changes[item.rev].author ?>:</span>
       <span class="change"><?cs var:browser.changes[item.rev].message ?></span>
      </td>
     </tr>
    <?cs /each ?>
   </tbody>
  </table><?cs
 /if ?><?cs

 if:len(browser.props) || !browser.is_dir ?>
  <table id="info" summary="Revision info"><?cs
   if:!browser.is_dir ?><tr>
    <th scope="col">
     Revision <a href="<?cs var:file.changeset_href ?>"><?cs var:file.rev ?></a>, <?cs var:file.size ?>
     (checked in by <?cs var:file.author ?>, <?cs var:file.age ?> ago)
    </th></tr><tr>
    <td class="message"><?cs var:file.message ?></td>
   </tr><?cs /if ?><?cs
   if:len(browser.props) ?><tr>
    <td colspan="2"><ul class="props"><?cs
     each:prop = browser.props ?>
      <li>Property <strong><?cs var:prop.name ?></strong> set to <em><code><?cs
      var:prop.value ?></code></em></li><?cs
     /each ?>
    </ul></td></tr><?cs
   /if ?>
  </table><?cs
 /if ?><?cs
 
 if:!browser.is_dir ?>
  <div id="preview"><?cs
   if:file.preview ?><?cs
    var:file.preview ?><?cs
   elif:file.max_file_size_reached ?>
    <strong>HTML preview not available</strong>, since the file size exceeds
    <?cs var:file.max_file_size ?> bytes. Try <a href="<?cs
    var:file.raw_href ?>">downloading</a> the file instead.<?cs
   else ?><strong>HTML preview not available</strong>. To view, <a href="<?cs
    var:file.raw_href ?>">download</a> the file.<?cs
   /if ?>
  </div><?cs
 /if ?>

 <div id="help">
  <strong>Note:</strong> See <a href="<?cs var:trac.href.wiki
  ?>/TracBrowser">TracBrowser</a> for help on using the browser.
 </div>

  <div id="anydiff">
   <form action="<?cs var:browser.anydiff_href ?>" method="get">
    <div class="buttons">
     <input type="hidden" name="new_path" value="<?cs var:browser.path ?>" />
     <input type="hidden" name="old_path" value="<?cs var:browser.path ?>" />
     <input type="hidden" name="new_rev" value="<?cs var:browser.revision ?>" />
     <input type="hidden" name="old_rev" value="<?cs var:browser.revision ?>" />
     <input type="submit" value="View changes..." title="Prepare an Arbitrary Diff" />
    </div>
   </form>
  </div>

</div>
</div>
<?cs include:"footer.cs"?>
