from pydantic import BaseModel, Field, model_validator


class AuthLoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    master_key: str | None = None
    device_label: str = Field(min_length=1)
    device_fingerprint: str | None = None
    platform: str | None = None

    @model_validator(mode="after")
    def require_email_password_or_master_key(self) -> "AuthLoginRequest":
        has_email_password = bool(self.email and self.password)
        has_master_key = bool(self.master_key)

        if has_email_password == has_master_key:
            raise ValueError("Login requires either email+password or master_key, but not both.")

        return self


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
    device_id: str = Field(min_length=1)


class AuthLogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
    device_id: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    device_id: str


class AuthLogoutResponse(BaseModel):
    status: str
