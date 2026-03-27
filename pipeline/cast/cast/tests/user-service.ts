/**
 * user-service.ts
 * ---------------
 * User management service — cAST TypeScript example.
 */

export interface User {
    id: string;
    email: string;
    displayName: string;
    role: "admin" | "user" | "guest";
    createdAt: Date;
}

export interface UserRepository {
    findById(id: string): Promise<User | null>;
    findByEmail(email: string): Promise<User | null>;
    save(user: User): Promise<User>;
    delete(id: string): Promise<boolean>;
}

export type CreateUserInput = Pick<User, "email" | "displayName" | "role">;

export class UserService {
    private readonly repo: UserRepository;

    constructor(repo: UserRepository) {
        this.repo = repo;
    }

    async createUser(input: CreateUserInput): Promise<User> {
        const existing = await this.repo.findByEmail(input.email);
        if (existing) {
            throw new Error(`Email ${input.email} is already registered`);
        }
        const user: User = {
            id:          crypto.randomUUID(),
            email:       input.email.toLowerCase().trim(),
            displayName: input.displayName.trim(),
            role:        input.role,
            createdAt:   new Date(),
        };
        return this.repo.save(user);
    }

    async getUserById(id: string): Promise<User> {
        const user = await this.repo.findById(id);
        if (!user) throw new Error(`User ${id} not found`);
        return user;
    }

    async updateRole(userId: string, newRole: User["role"]): Promise<User> {
        const user = await this.getUserById(userId);
        return this.repo.save({ ...user, role: newRole });
    }

    async deleteUser(userId: string): Promise<void> {
        const deleted = await this.repo.delete(userId);
        if (!deleted) throw new Error(`Failed to delete user ${userId}`);
    }
}

export function isAdminUser(user: User): boolean {
    return user.role === "admin";
}

export const formatUserLabel = (user: User): string =>
    `${user.displayName} <${user.email}>`;
