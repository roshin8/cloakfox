/* MPL-2.0. Only the signed Multi-Account Containers popup may use this bridge. */
export class CloakfoxContainerProxyEditorParent extends JSWindowActorParent {
  async receiveMessage(message) {
    if (this.manager.documentPrincipal.addonId!=='@testpilot-containers' ||
        new URL(this.manager.documentURI.spec).pathname!=='/popup.html') throw new Error('Not the container proxy editor.');
    const api=ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs');
    if (message.name==='Read') return api.readMACProxy(message.data);
    if (message.name==='Save') return api.saveMACProxy(message.data);
    const bulk=ChromeUtils.importESModule('resource:///modules/CloakfoxContainerBulk.sys.mjs');
    if(message.name==='BulkList')return bulk.listBulkContainers();
    if(message.name==='BulkProxy')return bulk.applyBulkProxy(message.data);
    if(message.name==='BulkDeleteReview'){
      const plan=bulk.prepareBulkDelete(message.data.ids);
      const token=Services.uuid.generateUUID().toString();
      this.deleteReview={token,plan};
      return {token,containers:plan};
    }
    if(message.name==='BulkDeleteConfirm'){
      const review=this.deleteReview;this.deleteReview=null;
      if(!review || message.data.token!==review.token)throw new Error('Review the selected containers before deleting.');
      return bulk.deleteBulkContainers(review.plan);
    }
    throw new Error('Unknown proxy editor request.');
  }
}
