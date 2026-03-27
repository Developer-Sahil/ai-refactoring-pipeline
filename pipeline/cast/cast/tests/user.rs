pub struct User {
    id: i32,
    name: String,
}

impl User {
    pub fn new(id: i32, name: String) -> Self {
        User { id, name }
    }
}
