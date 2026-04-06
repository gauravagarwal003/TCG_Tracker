# Firestore Security Rules

Use this as the canonical production ruleset for this repository.

Firebase Console path:

1. Firestore Database -> Rules
2. Replace existing rules
3. Publish

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    function signedIn() {
      return request.auth != null;
    }

    function isOwner(userId) {
      return signedIn() && request.auth.uid == userId;
    }

    function validDocIdFromFields(docId, categoryId, groupId, productId) {
      return docId == (string(categoryId) + '_' + string(groupId) + '_' + string(productId));
    }

    function validActiveProductShape() {
      return request.resource.data.keys().hasOnly([
        'categoryId',
        'group_id',
        'product_id',
        'count',
        'users',
        'last_updated'
      ])
      && request.resource.data.categoryId is string
      && request.resource.data.group_id is string
      && request.resource.data.product_id is string
      && request.resource.data.count is number
      && request.resource.data.count >= 0
      && request.resource.data.users is list
      && request.resource.data.last_updated is string;
    }

    function validProductMappingShape() {
      return request.resource.data.keys().hasOnly([
        'name',
        'product_id',
        'group_id',
        'categoryId',
        'imageUrl',
        'url',
        'updated_at',
        'created_at'
      ])
      && request.resource.data.name is string
      && request.resource.data.name.size() > 0
      && request.resource.data.name.size() <= 200
      && request.resource.data.product_id is string
      && request.resource.data.group_id is string
      && request.resource.data.categoryId is number
      && request.resource.data.imageUrl is string
      && request.resource.data.url is string
      && request.resource.data.updated_at is string;
    }

    match /users/{userId} {
      // Keep parent doc locked unless you explicitly use it.
      allow read, write: if false;

      match /transactions/{txnId} {
        allow read, write: if isOwner(userId);
      }

      match /holdings/{holdingId} {
        allow read, write: if isOwner(userId);
      }

      match /meta/{metaId} {
        allow read, write: if isOwner(userId);
      }
    }

    // Shared union index for scheduler and authenticated client reads.
    match /active_products/{docId} {
      allow read: if signedIn();
      allow write: if signedIn()
        && validActiveProductShape()
        && validDocIdFromFields(
          docId,
          request.resource.data.categoryId,
          request.resource.data.group_id,
          request.resource.data.product_id
        );
    }

    // Shared mapping metadata used by product search/autocomplete.
    match /product_mappings/{docId} {
      allow read: if signedIn();
      allow write: if signedIn()
        && validProductMappingShape()
        && docId == (request.resource.data.group_id + '_' + request.resource.data.product_id);
    }

    // Default deny for anything not explicitly allowed above.
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

## Rule Summary

1. Users can only access their own `users/{uid}/...` subcollections.
2. `active_products` is readable and writable by authenticated users with strict shape/docId validation.
3. `product_mappings` is readable and writable by authenticated users with strict shape/docId validation.
4. Everything else is denied by default.

## Validation Checklist

Use Rules Simulator:

1. Read `users/userA/transactions/x` as `userA` -> allow
2. Read `users/userB/transactions/x` as `userA` -> deny
3. Write valid `active_products/{cat}_{gid}_{pid}` as authenticated user -> allow
4. Write invalid `active_products` doc (bad id/shape) -> deny
5. Write valid `product_mappings/{gid}_{pid}` as authenticated user -> allow
6. Write invalid `product_mappings` doc (bad id/shape) -> deny

